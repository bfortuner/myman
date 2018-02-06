import sys
import datetime
import json
import os
import time
import traceback

import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import backoff
import pandas as pd
from tenacity import retry
from tenacity import wait_exponential
from tenacity import stop_after_attempt

import punisher.constants as c
import punisher.config as cfg
from punisher.clients import s3_client
from punisher.exchanges import load_exchange
from punisher.data.store import FileStore
from punisher.feeds import OHLCVExchangeFeed
from punisher.feeds import ohlcv_feed
from punisher.portfolio.asset import Asset
from punisher.utils.dates import Timeframe
from punisher.utils.dates import str_to_date
import punisher.utils.logger as logger_utils

parser = argparse.ArgumentParser(description='OHLCV Fetcher')
parser.add_argument('-ex', '--exchange', help='one exchange id', type=str)
parser.add_argument('-sym', '--symbol', help='one symbol', type=str)
parser.add_argument('-t', '--timeframe', help='length of period (1m, 30m, 1h, 1d)', default='30m', type=str)
parser.add_argument('--start', help='start time yyyy-mm-dd', default=None, type=str)
parser.add_argument('--end', help='end time yyyy-mm-dd', default=None, type=str)
parser.add_argument('--action', help='"fetch" from exchange or "download" from s3', choices=['fetch','download'])
parser.add_argument('--upload', help='upload to s3 after fetching from exchange', action='store_true')
parser.add_argument('--refresh', help='sleep seconds for rate limit', default=5, type=int)
parser.add_argument('--outdir', help='output directory to save files', default=cfg.DATA_DIR, type=str)

# python -m punisher.data.ohlcv_fetcher -ex gdax -sym BTC/USD -t 1h --action download

args = parser.parse_args()
OHLCV = 'ohlcv'
OHLCV_DIR = Path(args.outdir, OHLCV)
OHLCV_DIR.mkdir(exist_ok=True)

def get_rotating_ohlcv_fname(ex_id, asset, timeframe, start):
    fname = '{:s}_{:s}_{:s}_{:d}_{:d}_{:d}.csv'.format(
        ex_id, asset.id, timeframe.id, start.year,
        start.month, start.day
    )
    return fname

def get_rotating_ohlcv_fpath(ex_id, asset, timeframe, start, outdir=OHLCV_DIR):
    fname = get_rotating_ohlcv_fname(ex_id, asset, timeframe, start)
    return Path(outdir, fname)

def get_s3_path(ex_id, asset, timeframe, start):
    fname = get_rotating_ohlcv_fname(ex_id, asset, timeframe, start)
    return OHLCV + '/' + fname

def upload_to_s3(ex_id, asset, timeframe, start):
    fpath = get_rotating_ohlcv_fpath(ex_id, asset, timeframe, start)
    s3_path = get_s3_path(ex_id, asset, timeframe, start)
    print('Uploading to s3:', s3_path)
    s3_client.upload_file(str(fpath), s3_path)

# https://pypi.python.org/pypi/backoff
@backoff.on_exception(backoff.expo,
                      Exception,
                      on_backoff=logger_utils.retry_hdlr,
                      max_tries=10)
def fetch_and_save(ex_id, asset, timeframe, start, end):
    exchange = load_exchange(ex_id)
    df = ohlcv_feed.fetch_asset(exchange, asset, timeframe, start, end)
    fpath = get_rotating_ohlcv_fpath(ex_id, asset, timeframe, start)
    df.to_csv(fpath, index=True)
    return df

def fetch_once(ex_id, asset, timeframe, start, end, upload, refresh):
    out_fpath = ohlcv_feed.get_ohlcv_fpath(asset, ex_id, timeframe)
    out_df = None
    df = None
    while end - start > timeframe.delta:
        print("Start:", start, "End:", end)

        df = fetch_and_save(ex_id, asset, timeframe, start, end)
        print("Downloaded:", len(df))
        if len(df) == 0:
            raise Exception("No Data In this Time Range!")

        if out_df is None:
            out_df = df
        else:
            out_df = merge_dfs(out_df, df)
        out_df.to_csv(out_fpath, index=True)

        if upload:
            upload_to_s3(ex_id, asset, timeframe, start)

        start = df[['utc']].max()[0] + timeframe.delta
        time.sleep(refresh)
    return df, start

def fetch_forever(exchange_id, asset, timeframe, start, end, upload, refresh):
    while True:
        df, start = fetch_once(
            exchange_id, asset, timeframe,
            start, end, upload, refresh)
        end = datetime.datetime.utcnow()

def download(ex_id, asset, timeframe):
    prefix = 'ohlcv/'+ex_id+'_'+asset.id+'_'+timeframe.id
    keys = s3_client.list_files(prefix=prefix)
    fpaths = []
    for key in keys:
        fpath = Path(OHLCV_DIR, Path(key).name)
        fpaths.append(fpath)
        print("Downloading", fpath)
        s3_client.download_file(str(fpath), key)
    merge_files(fpaths, ex_id, asset, timeframe, cleanup=True)

def merge_dfs(df1, df2):
    df = pd.concat([df1, df2])
    df = df[~df.index.duplicated(keep='last')]
    return df

def merge_files(fpaths, ex_id, asset, timeframe, cleanup=False):
    out_fpath = ohlcv_feed.get_ohlcv_fpath(asset, ex_id, timeframe)
    out_df = ohlcv_feed.load_asset(fpaths[0])
    for fpath in fpaths[1:]:
        df = ohlcv_feed.load_asset(fpath)
        out_df = merge_dfs(out_df, df)
    if cleanup:
        _ = [os.remove(f) for f in fpaths]
    out_df.to_csv(out_fpath, index=True)


if __name__ == "__main__":
    default_start = datetime.datetime(year=2017, month=1, day=1)
    exchange_id = args.exchange
    asset = Asset.from_symbol(args.symbol)
    timeframe = Timeframe.from_id(args.timeframe)
    start = str_to_date(args.start) if args.start is not None else default_start
    end = str_to_date(args.end) if args.end is not None else None
    action = args.action
    upload = args.upload
    refresh = args.refresh
    if action == 'fetch':
        print('Fetching OHLCV from exchange: ', exchange_id,
               'Asset:', asset.symbol, 'timeframe:', timeframe.id,
               'start:', start, 'end:', end, 'refresh:', refresh)
        if end is None:
            print("Running forever!")
            end = datetime.datetime.utcnow()
            fetch_forever(exchange_id, asset, timeframe, start, end, upload, refresh)
        else:
            print("Backfilling!")
            fetch_once(exchange_id, asset, timeframe, start, end, upload, refresh)
    elif action == 'download':
        print('Downloading OHLCV from S3. ExchangeId:', exchange_id,
               'Asset:', asset.symbol, 'timeframe:', timeframe.id)
        download(exchange_id, asset, timeframe)
    else:
        raise Exception("Action {:s} not supported!".format(action))
