# version 1.1
import logging
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from icecream import ic
from .serializers import (
    adxSerializer,
    adx_profit_loss_serializer,
    adx_stats_serializer,
    add_robot_data_serializer,
)
from .models import adx, adx_profit_loss, adx_stats, send_signals
from category.models import Category

from django.db.models import Q
from datetime import datetime as dt, time
from datetime import timedelta
import pygsheets
import pandas as pd
import numpy as np
from pathlib import Path
import json
import pytz
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time as ti

from telegram_notifier import TelegramNotifier
import socket

from localStoragePy import localStoragePy
localStorage = localStoragePy("restserver", "sqlite")

from channels.layers import get_channel_layer
from celery import shared_task

channel_layer = get_channel_layer()


from adx.robotscanner import RobotScanner
from adx.models import adx, send_signals
from adx.serializers import adxSerializer, send_signals_serializer

from category.models import Category
from category.serializers import CategorySerializer

# from roboportfolio.models import roboportfolio,demo_trades
# from roboportfolio.serializers import RoboportfolioSerializer

from backtesting.models import  roboportfolio as backtesting_roboportfolio, backtesting_trades
from backtesting.serializers import  RoboportfolioSerializer as backtesting_RoboportfolioSerializer, backtesting_trades_serializer


from roboportfolio.models import userportfolio, roboportfolio, alpacaTransaction,demo_trades,demo_trades_profit_loss,portfolio_profit_loss
from roboportfolio.serializers import userportfolioSerializer, RoboportfolioSerializer as DemoRoboportfolioSerializer, demo_trades_serializer,demo_trades_profit_loss_serializer,portfolio_profit_loss_serializer

from roboportfoliolive.models import roboportfolio as roboportfoliolive, live_trades
from roboportfoliolive.serializers import RoboportfolioSerializer as LiveRoboportfolioSerializer, live_trades_serializer

from signals.models import roboportfolio as signal_roboportfolio, trades as signal_trades
from signals.serializers import RoboportfolioSerializer as SignalsRoboportfolioSerializer, trades_serializer as signals_trades_serializer

from backtesting.utils import graphviewpositive

from brokeralp.models import alpaca

from stockdata.models import stockdata
from stockdata.serializers import StockdataSerializer


from stockdata.models import stockdata

robotscanner = RobotScanner()

from datafeed.broker_alpaca import broker_alpaca

broker_alpaca = broker_alpaca()

from datafeed.tradeindicators import Tradeindicators

tradeindicators = Tradeindicators()



@shared_task()
def get_accountinfo_task(key, secret, endpoint, customer_id):
    response = broker_alpaca.alpaca_getaccount(key, secret, endpoint, customer_id)
    return response


@shared_task()
def alpaca_buy_task(
    self,
    key,
    secret,
    endpoint,
    customer_id,
    stock,
    asset_class,
    ttype,
    allocatedvalue,
    myportfolio_id,
):
    
    response = broker_alpaca.alpaca_dbbuyorder(
        key,
        secret,
        endpoint,
        customer_id,
        stock,
        asset_class,
        allocatedvalue,
        ttype,
        myportfolio_id,
    )
    return response


@shared_task()
def alpaca_sell_task(
    self, key, secret, endpoint, customer_id, stock, asset_class, ttype, myportfolio_id
):
    response = broker_alpaca.alpaca_dbsellorder(
        key, secret, endpoint, customer_id, stock, asset_class, ttype, myportfolio_id
    )
    return response


@shared_task()
def supertrend(df, atr_period=18, multiplier=3):

    atr_period = float(atr_period)
    multiplier = float(multiplier)
    # issue with forex --

    minclose = df.loc[0, "close"]
    if minclose < 2:
        high = df["high"] = df["high"] * 1000
        low = df["low"] = df["low"] * 1000
        close = df["close"] = df["close"] * 1000
    else:
        high = df["high"]
        low = df["low"]
        close = df["close"]
    # calculate ATR
    price_diffs = [high - low, high - close.shift(), close.shift() - low]
    tr = pd.concat(price_diffs, axis=1)
    tr = tr.abs().max(axis=1)

    df["tr"] = tr
    df["atr"] = atr = df["tr"].ewm(alpha=1 / atr_period, min_periods=atr_period).mean()

    # df["ema1"] = tradeindicators.ema(df["close"], 100)
    # df["ema2"] = tradeindicators.ema(df["close"], 200)

    # HL2 is simply the average of high and low prices
    df["hl2"] = hl2 = (high + low) / 2
    final_upperband = upperband = hl2 + (multiplier * atr)
    final_lowerband = lowerband = hl2 - (multiplier * atr)
    supertrend = [True] * len(df)
    trade = [True] * len(df)

    for i in range(1, len(df.index)):
        curr, prev = i, i - 1

        # if current close price crosses above upperband
        if close[curr] > final_upperband[prev]:
            supertrend[curr] = 1
        # if current close price crosses below lowerband
        elif close[curr] < final_lowerband[prev]:
            supertrend[curr] = 0
        # else, the trend continues
        else:
            supertrend[curr] = supertrend[prev]
            # adjustment to the final bands
            if supertrend[curr] == 1 and final_lowerband[curr] < final_lowerband[prev]:
                final_lowerband[curr] = final_lowerband[prev]
            if supertrend[curr] == 0 and final_upperband[curr] > final_upperband[prev]:
                final_upperband[curr] = final_upperband[prev]

            # remove bands depending on the trend direction for visualization
            if supertrend[curr] == 1:
                final_upperband[curr] = np.nan
            else:
                final_lowerband[curr] = np.nan

    df["supertrend"] = supertrend
    df["supertrend1"] = df["supertrend"].shift(periods=1)

    df["final_lowerband"] = final_lowerband
    df["final_upperband"] = final_upperband

    df = pd.DataFrame(df)
    df.reset_index(inplace=True)

    return df


@shared_task()
def supertrendc2(df, atr_period=18, multiplier=3):

    atr_period = float(atr_period)
    multiplier = float(multiplier)
    # issue with forex --

    minclose = df.loc[0, "c2"]
    if minclose < 2:
        high = df["h2"] = df["h2"] * 1000
        low = df["l2"] = df["l2"] * 1000
        close = df["c2"] = df["c2"] * 1000
    else:
        high = df["h2"]
        low = df["l2"]
        close = df["c2"]
    # calculate ATR
    price_diffs = [high - low, high - close.shift(), close.shift() - low]
    tr = pd.concat(price_diffs, axis=1)
    tr = tr.abs().max(axis=1)

    df["tr"] = tr
    df["atr"] = atr = df["tr"].ewm(alpha=1 / atr_period, min_periods=atr_period).mean()

    # df["ema1"] = tradeindicators.ema(df["close"], 100)
    # df["ema2"] = tradeindicators.ema(df["close"], 200)

    # HL2 is simply the average of high and low prices
    df["hl2"] = hl2 = (high + low) / 2
    final_upperband = upperband = hl2 + (multiplier * atr)
    final_lowerband = lowerband = hl2 - (multiplier * atr)
    supertrend = [True] * len(df)
    trade = [True] * len(df)

    for i in range(1, len(df.index)):
        curr, prev = i, i - 1

        # if current close price crosses above upperband
        if close[curr] > final_upperband[prev]:
            supertrend[curr] = 1
        # if current close price crosses below lowerband
        elif close[curr] < final_lowerband[prev]:
            supertrend[curr] = 0
        # else, the trend continues
        else:
            supertrend[curr] = supertrend[prev]
            # adjustment to the final bands
            if supertrend[curr] == 1 and final_lowerband[curr] < final_lowerband[prev]:
                final_lowerband[curr] = final_lowerband[prev]
            if supertrend[curr] == 0 and final_upperband[curr] > final_upperband[prev]:
                final_upperband[curr] = final_upperband[prev]

            # remove bands depending on the trend direction for visualization
            if supertrend[curr] == 1:
                final_upperband[curr] = np.nan
            else:
                final_lowerband[curr] = np.nan

    df["supertrendc2"] = supertrend
    df["supertrend1"] = df["supertrend"].shift(periods=1)

    df["finalc2_lowerband"] = final_lowerband
    df["finalc2_upperband"] = final_upperband

    df = pd.DataFrame(df)
    df.reset_index(inplace=True)

    return df


@shared_task()
def renko(df, atr_period=18, multiplier=3):

    atr_period = float(atr_period)
    multiplier = float(multiplier)

    minclose = df.loc[0, "close"]
    if minclose < 2:
        high = df["high"] = df["high"] * 1000
        low = df["low"] = df["low"] * 1000
        close = df["close"] = df["close"] * 1000
    else:
        high = df["high"]
        low = df["low"]
        close = df["close"]

    # calculate ATR
    price_diffs = [high - low, high - close.shift(), close.shift() - low]
    tr = pd.concat(price_diffs, axis=1)
    tr = tr.abs().max(axis=1)
    df["tr"] = tr
    df["atr"] = atr = df["tr"].ewm(alpha=1 / atr_period, min_periods=atr_period).mean()
    atrsize = df["atr"].iloc[-1]
    # atrsize = 8

    hf = tradeindicators.bricks_series(df, atrsize)

    hf["HMA50"] = tradeindicators.hma(hf["renko"], 15)
    hf["HMA50"] = hf["HMA50"].round(2)
    hf = tradeindicators.minmaxhma(hf)

    # hf['cmax'] = hf['hfema'][(hf['hfema'].shift(1) < hf['hfema']) & (hf['hfema'].shift(-1) < hf['hfema'])]
    # hf['cmin'] = hf['hfema'][(hf['hfema'].shift(1) > hf['hfema']) & (hf['hfema'].shift(-1) > hf['hfema'])]

    return hf


@shared_task()
def strategy80_running(stock, source, categoryId,minloss=0.99,minprofit=1.01,meantrade=1,timing=3, atr_period=18, multiplier=3,tradetype=0,backtest=1,myportfolio_id=1):
    
    stockdataInstance = stockdata.objects.filter(stock=stock).last()
    stockserializer = StockdataSerializer(stockdataInstance)
    
    
    meantrade = stockserializer.data["meantrade"]
    pos = stockserializer.data["pos"]
    neg = stockserializer.data["neg"]
    timing = stockserializer.data["timing"]
    slowanchorma = stockserializer.data["slowanchorma"]
    veryslowanchorma = stockserializer.data["veryslowanchorma"]

    ic(meantrade,pos,neg)
    
    ic(stock,timing,myportfolio_id,pos,neg)
    if timing == timing :
        af = robotscanner.get_1min_data(stock, source)
    if timing == timing:
        af = robotscanner.get_3min_data(stock, source)
    elif timing == timing :
        af = robotscanner.get_5min_data(stock, source)
    elif timing == timing:
        af = robotscanner.get_15min_data(stock, source)


    af = robotscanner.get_slowmovingaverage(af)
    af = robotscanner.pullback_avg(af,slowanchorma,veryslowanchorma)
    af = robotscanner.new_indicators(af)
    af = robotscanner.analysis1(af,meantrade)
    af = robotscanner.minmaxc2(af)
    af['HMA50'] =  af['c2']
    af["org_id"] = 1
    af["stock"] = stock
    af["source"] = source
    af["myportfolio_id"] = 1
    af["rmin"] = af['cmin']
    af['rmax'] = af['cmax']
    af["myportfolio_id"] = myportfolio_id
    df = strategy2_running(stock,myportfolio_id, af, 3, 1,minloss,minprofit,pos,neg,tradetype,backtest)
    # graphviewpositive(stock,df)
    return df


@shared_task()
def trade_signal(self, stock,myportfolio_id,data, type):
    print(type)
    if type=="backtesting":
        ic("backtesting trade")
        backtestingtradeInstance = backtesting_roboportfolio.objects.filter(stock=stock,myportfolio_id=myportfolio_id, status=1)
        BacktestingRoboportfolioSerializer = backtesting_RoboportfolioSerializer(backtestingtradeInstance,many=True)

        for trade in BacktestingRoboportfolioSerializer.data:
            data["roboportfolioId"] = trade['id']
            data["customer_id"] = trade['customer_id']
            data["myportfolio_id"] = trade['myportfolio_id']
            

            if data["signals"] == 'BUY' or data["signals"] == 'SELL':
                data["qty"] = round(trade['allocatedvalue']/data["price"] ,4)
                data["startvalue"] = trade['allocatedvalue']
                data["endvalue"] = 0
                _myportfolio_stock_startvalue = str(trade['id'])  + "_startvalue"
                _myportfolio_stock_qty = str(trade['id']) + "_qty"
                localStorage.setItem(_myportfolio_stock_startvalue, data["startvalue"])
                localStorage.setItem(_myportfolio_stock_qty, data["qty"])

            if data["signals"] == 'BUYCLOSE' or data["signals"] == 'SELLCLOSE':
                _myportfolio_stock_startvalue = str(trade['id'])  + "_startvalue"
                _myportfolio_stock_qty = str(trade['id']) + "_qty"
                startvalue = localStorage.getItem(_myportfolio_stock_startvalue)
                qty = localStorage.getItem(_myportfolio_stock_qty)

                data["startvalue"] = startvalue
                data["endvalue"] = round(float(data["price"]) * float(qty),2)
                data["qty"] = qty
                if data["signals"] == 'BUYCLOSE':
                    data["profitloss"] = round(data["endvalue"] - float(startvalue),2)
                elif data["signals"] == 'SELLCLOSE':
                    data["profitloss"] = round(float(startvalue) - data["endvalue"],2)

    

            print(data)
            serializer = backtesting_trades_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                # print(type,data,serializer.data["id"])
                #  Let's update the portfolio balance.
                backtesting_trades_instance = backtesting_trades.objects.filter(stock=stock,myportfolio_id=myportfolio_id)
                serializer = backtesting_trades_serializer(backtesting_trades_instance,many=True)
                profitloss = 0 
                winrate = 0 
                totaltrades = 0
                percentage_win = 0
                for data in serializer.data:
                    if data['signals'] == 'BUYCLOSE' or data['signals'] == 'SELLCLOSE':
                        profitloss = profitloss + float(data['profitloss'])
                        totaltrades = totaltrades + 1
                        if float(data['profitloss']) > 0:
                            winrate = winrate + 1
                        
                if winrate > 0:
                    percentage_win = round(winrate / totaltrades * 100, 2)

                
                
                percentage_profit = round(profitloss / trade['allocatedvalue'] * 100, 2)
                print("percentage_profit", percentage_profit)
                stock_portfolio_profitloss = profitloss
                
                updatestock = {}
                updatestock['profitloss'] = round(stock_portfolio_profitloss,2)
                updatestock['percentagepnl'] = percentage_profit
                updatestock['winrate'] = winrate
                updatestock['totaltrades'] = totaltrades
                updatestock['percentagewin'] = round(percentage_win,2)
            
                    
                RoboportfolioInstance = backtesting_roboportfolio.objects.get(myportfolio_id=myportfolio_id,stock=data['stock'])
                updateserializer = backtesting_RoboportfolioSerializer(RoboportfolioInstance, data=updatestock,partial=True)
                if updateserializer.is_valid():
                    updateserializer.save()
                    print("updateserializer updated")
                else:
                    print(updateserializer.errors)

            else:
                print(serializer.errors)
    elif type=="demo":
        demotradeInstance = roboportfolio.objects.filter(stock=stock,status=1)
        demotradeserializer = DemoRoboportfolioSerializer(demotradeInstance,many=True)

        for trade in demotradeserializer.data:
            data["roboportfolioId"] = trade['id']
            data["customer_id"] = trade['customer_id']
            data["myportfolio_id"] = trade['myportfolio_id']
            serializer = demo_trades_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)

    elif type=="live":
        livetradeInstance = roboportfoliolive.objects.filter(stock=stock,status=1)
        livetradeserializer = LiveRoboportfolioSerializer(livetradeInstance,many=True)

        for trade in livetradeserializer.data:
            data["roboportfolioId"] = trade['id']
            data["customer_id"] = trade['customer_id']
            data["myportfolio_id"] = trade['myportfolio_id']

            serializer = live_trades_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            
            else:
                print(serializer.errors)
                
    elif type=="signals":
        livetradeInstance = signal_roboportfolio.objects.filter(stock=stock,status=1)
        livetradeserializer = SignalsRoboportfolioSerializer(livetradeInstance,many=True)

        for trade in livetradeserializer.data:
            data["roboportfolioId"] = trade['id']
            data["customer_id"] = trade['customer_id']
            data["myportfolio_id"] = trade['myportfolio_id']
            serializer = signals_trades_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)
                
@shared_task()
def send_telegram_signal(self, message, chat_id):
    IP_address = socket.gethostbyname(socket.gethostname())
    website = "https://www.iamstockbot.com"
    message = message + "\n " + str(website) 
    chat_id = int(chat_id)
    token = "5414461112:AAHUWey8c-PQXnAyGJI2W_nA_isziVoT26M"
    # debug_chat_id = -1001763597956
    # chat_id = debug_chat_id
    notifier = TelegramNotifier(token, parse_mode="HTML", chat_id=chat_id)
    try:
        notifier.send(message)
        return True
    except:
        print("Telegram timeout")
        return False


@shared_task()
def save2googlesheet(df, sheetname, sheetnumber):
    numberofrows = len(df.index)
    if numberofrows > 1500:
        df = df.iloc[-1500:]

    df = df.iloc[::-1]
    current_dir = str(Path(__file__).parent)
    filename = "gsheets.json"
    filename = current_dir + "/" + filename
    gc = pygsheets.authorize(service_file=filename)
    sh = gc.open(sheetname)
    wks1 = sh[sheetnumber]
    wks1.clear()
    wks1.set_dataframe(df, (0, 0))


@shared_task()
def supertrend2db(stock, df, type):

    df["json"] = df.to_json(
        orient="records", date_format="iso", date_unit="s", lines=True
    ).splitlines()
    for i in range(len(df.index)):
        serializer = adxSerializer(data=json.loads(df.loc[i, "json"]))
        if serializer.is_valid():
            serializer.save()
        else:
            print(serializer.errors)
    return df

@shared_task()
def supertrend2db_running(df,timing):
    df["json"] = df.to_json(orient="records", date_format="iso", date_unit="s", lines=True).splitlines()
    size = len(df.index)
    if timing == 1:
        loopsize = 3
    if timing == 3:
        loopsize = 1
    if timing == 5:
        loopsize = 5
    else:
        loopsize = 3
    for r in range(loopsize,0,-1):
       
        i = size - r
        serializer = adxSerializer(data=json.loads(df.loc[i, "json"]))
        if serializer.is_valid():
            serializer.save()
        else:
            print(serializer.errors)
    print("supertrend2db_running completed")    
    return df


@shared_task()
def trigger_alpacarobot(stock, signal, asset_class):
    ic("trigger_alpacarobot", stock, signal, asset_class)
    # get stock info
    items = adx.objects.filter(stock=stock).order_by("-id")[:1]
    serializer = adxSerializer(items, many=True)
    items = list(serializer.data)

    if signal == "BUY":
        apiInstance = roboportfolio.objects.filter(
            stock=stock, broker="Alpaca", status="1"
        ).extra(
            select={
                "stock": '"roboportfolio"."stock"',
                "customer_id": '"roboportfolio"."customer_id"',
                "api_endpoint": '"t1"."api_endpoint"',
                "api_key": '"t1"."api_key"',
                "api_secret": '"t1"."api_secret"',
                "robo_cust_id": '"roboportfolio"."customer_id"',
                "myportfolio_id": '"roboportfolio"."myportfolio_id"',
                "portfolio_id": '"roboportfolio"."portfolio_id"',
                "portfolio_name": '"roboportfolio"."portfolio_name"',
                "portfolio_stock": '"roboportfolio"."stock"',
                "allocatedpercentage": '"roboportfolio"."allocatedpercentage"',
                "allocatedqty": '"roboportfolio"."allocatedqty"',
                "allocatedvalue": '"roboportfolio"."allocatedvalue"',
                "startprice": '"roboportfolio"."startprice"',
                "presentvalue": '"roboportfolio"."presentvalue"',
                "totalvalue": '"roboportfolio"."totalvalue"',
                "status": '"roboportfolio"."status"',
                "broker": '"roboportfolio"."broker"',
            },
            tables=['"alpaca" AS "t1"'],
            where=['"roboportfolio"."customer_id"="t1"."customer_id"'],
        )

        print(apiInstance.query)

        for data in apiInstance.iterator():
            print("apiinstance ------------ ")
            print(data.customer_id)
            print(data.allocatedvalue)
            print(data.allocatedqty)
            print(data.broker)
            print(data.api_endpoint)
            print(data.api_key)
            print(data.api_secret)
            print(data.stock)
            print("robo_cust_id", data.robo_cust_id)
            print("myportfolio_id", data.myportfolio_id)
            print("apiinstance ------------- ")
            key = data.api_key
            secret = data.api_secret
            endpoint = data.api_endpoint
            customer_id = data.customer_id
            stockname = data.stock
            stock = stockdata.objects.get(stock=stockname).alpaca
            allocatedvalue = data.allocatedvalue
            ttype = "BUY"
            alpaca_buy_task(
                "param",
                key,
                secret,
                endpoint,
                customer_id,
                stock,
                asset_class,
                ttype,
                data.allocatedvalue,
                data.myportfolio_id,
            )
            ti.sleep(2)

    if signal == "BUYCLOSE":
        apiInstance = roboportfolio.objects.filter(stock=stock, broker="Alpaca").extra(
            select={
                "stock": '"roboportfolio"."stock"',
                "customer_id": '"roboportfolio"."customer_id"',
                "api_endpoint": '"t1"."api_endpoint"',
                "api_key": '"t1"."api_key"',
                "api_secret": '"t1"."api_secret"',
                "robo_cust_id": '"roboportfolio"."customer_id"',
                "myportfolio_id": '"roboportfolio"."myportfolio_id"',
                "portfolio_id": '"roboportfolio"."portfolio_id"',
                "portfolio_name": '"roboportfolio"."portfolio_name"',
                "portfolio_stock": '"roboportfolio"."stock"',
                "allocatedpercentage": '"roboportfolio"."allocatedpercentage"',
                "allocatedqty": '"roboportfolio"."allocatedqty"',
                "allocatedvalue": '"roboportfolio"."allocatedvalue"',
                "startprice": '"roboportfolio"."startprice"',
                "presentvalue": '"roboportfolio"."presentvalue"',
                "totalvalue": '"roboportfolio"."totalvalue"',
                "status": '"roboportfolio"."status"',
                "broker": '"roboportfolio"."broker"',
            },
            tables=['"alpaca" AS "t1"'],
            where=['"roboportfolio"."customer_id"="t1"."customer_id"'],
        )

        ic(apiInstance.query)

        for data in apiInstance.iterator():
            print("line - 763 - apiinstance check for customer id  ------------ ")
            print(data.customer_id)
            print(data.allocatedvalue)
            print(data.allocatedqty)
            print(data.broker)
            print(data.api_endpoint)
            print(data.api_key)
            print(data.api_secret)
            print(data.stock)
            print("apiinstance ------------- ")
            key = data.api_key
            secret = data.api_secret
            endpoint = data.api_endpoint
            customer_id = data.customer_id
            stockname = data.stock
            stock = stockdata.objects.get(stock=stockname).alpaca
            ttype = "BUYCLOSE"
            alpaca_sell_task(
                "param",
                key,
                secret,
                endpoint,
                customer_id,
                stock,
                asset_class,
                ttype,
                data.myportfolio_id,
            )

    if signal == "SELL":
        if asset_class == "stock":
            apiInstance = roboportfolio.objects.filter(
                stock=stock, broker="Alpaca"
            ).extra(
                select={
                    "stock": '"roboportfolio"."stock"',
                    "customer_id": '"roboportfolio"."customer_id"',
                    "api_endpoint": '"t1"."api_endpoint"',
                    "api_key": '"t1"."api_key"',
                    "api_secret": '"t1"."api_secret"',
                    "robo_cust_id": '"roboportfolio"."customer_id"',
                    "myportfolio_id": '"roboportfolio"."myportfolio_id"',
                    "portfolio_id": '"roboportfolio"."portfolio_id"',
                    "portfolio_name": '"roboportfolio"."portfolio_name"',
                    "portfolio_stock": '"roboportfolio"."stock"',
                    "allocatedpercentage": '"roboportfolio"."allocatedpercentage"',
                    "allocatedqty": '"roboportfolio"."allocatedqty"',
                    "allocatedvalue": '"roboportfolio"."allocatedvalue"',
                    "startprice": '"roboportfolio"."startprice"',
                    "presentvalue": '"roboportfolio"."presentvalue"',
                    "totalvalue": '"roboportfolio"."totalvalue"',
                    "status": '"roboportfolio"."status"',
                    "broker": '"roboportfolio"."broker"',
                },
                tables=['"alpaca" AS "t1"'],
                where=['"roboportfolio"."customer_id"="t1"."customer_id"'],
            )
            print(apiInstance)

            for data in apiInstance.iterator():
                print(
                    "line - 808 - sell - apiinstance check for customer id  ------------ "
                )
                print(data.customer_id)
                print(data.allocatedvalue)
                print(data.allocatedqty)
                print(data.broker)
                print(data.api_endpoint)
                print(data.api_key)
                print(data.api_secret)
                print(data.stock)
                key = data.api_key
                secret = data.api_secret
                endpoint = data.api_endpoint
                customer_id = data.customer_id
                stockname = data.stock
                stock = stockdata.objects.get(stock=stockname).alpaca
                ttype = "SELL"
                alpaca_buy_task(
                    "param",
                    key,
                    secret,
                    endpoint,
                    customer_id,
                    stock,
                    asset_class,
                    ttype,
                    data.allocatedvalue,
                    data.myportfolio_id,
                )
                ti.sleep(2)

    if signal == "SELLCLOSE":
        if asset_class == "stock":
            apiInstance = roboportfolio.objects.filter(
                stock=stock, broker="Alpaca"
            ).extra(
                select={
                    "stock": '"roboportfolio"."stock"',
                    "customer_id": '"roboportfolio"."customer_id"',
                    "api_endpoint": '"t1"."api_endpoint"',
                    "api_key": '"t1"."api_key"',
                    "api_secret": '"t1"."api_secret"',
                    "robo_cust_id": '"roboportfolio"."customer_id"',
                    "myportfolio_id": '"roboportfolio"."myportfolio_id"',
                    "portfolio_id": '"roboportfolio"."portfolio_id"',
                    "portfolio_name": '"roboportfolio"."portfolio_name"',
                    "portfolio_stock": '"roboportfolio"."stock"',
                    "allocatedpercentage": '"roboportfolio"."allocatedpercentage"',
                    "allocatedqty": '"roboportfolio"."allocatedqty"',
                    "allocatedvalue": '"roboportfolio"."allocatedvalue"',
                    "startprice": '"roboportfolio"."startprice"',
                    "presentvalue": '"roboportfolio"."presentvalue"',
                    "totalvalue": '"roboportfolio"."totalvalue"',
                    "status": '"roboportfolio"."status"',
                    "broker": '"roboportfolio"."broker"',
                },
                tables=['"alpaca" AS "t1"'],
                where=['"roboportfolio"."customer_id"="t1"."customer_id"'],
            )

            print(apiInstance)
            for data in apiInstance.iterator():
                print(
                    "line - 851 - sellclose - apiinstance check for customer id  ------------ "
                )
                print(data.customer_id)
                print(data.allocatedvalue)
                print(data.allocatedqty)
                print(data.broker)
                print(data.api_endpoint)
                print(data.api_key)
                print(data.api_secret)
                print(data.stock)
                key = data.api_key
                secret = data.api_secret
                endpoint = data.api_endpoint
                customer_id = data.customer_id
                stockname = data.stock
                stock = stockdata.objects.get(stock=stockname).alpaca
                allocatedvalue = data.allocatedvalue
                ttype = "SELLCLOSE"
                alpaca_buy_task(
                    "param",
                    key,
                    secret,
                    endpoint,
                    customer_id,
                    stock,
                    asset_class,
                    ttype,
                    data.allocatedvalue,
                    data.myportfolio_id,
                )


@shared_task()
def delete_adx_data():
    adx.objects.all().delete()
    adx_profit_loss.objects.all().delete()
    adx_stats.objects.all().delete()
    # send_signals.objects.all().delete()
    # Category.objects.filter(id=67).delete()


@shared_task()
def delete_localstorage_date():
    localStorage.clear()


@shared_task()
def is_time_between(begin_time, end_time, check_time=None):
    # If check time is not given, default to current UTC time
    check_time = check_time or dt.utcnow().time()
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else:  # crosses midnight
        return check_time >= begin_time or check_time <= end_time


@shared_task()
def stocklist_running(debug):
    i = 1 
    starttime = dt.utcnow() + timedelta(hours=8)
    for i in range(9):
        categoryId = i
        if categoryId == 1 or categoryId == 2:
            print("category 1 - usa ")
            portfolioInstance = stockdata.objects.filter(portfolioId=categoryId)
            usatime = dt.utcnow() + timedelta(hours=-5)
            day = usatime.weekday()
            usatime = usatime.time()
            # sgttime = dt.utcnow() + timedelta(hours=8)
            # day = sgttime.weekday()
            # sgttime = sgttime.time()
            # if day < 7 and is_time_between(time(6,00), time(4,00),sgttime):
            if day < 6 and is_time_between(time(9, 30), time(16, 00), usatime):
                print("USA Market Hours is working" + str(usatime))
                usastocks = 1
                for data in portfolioInstance:
                    # if data.stock=='TQQQ':
                    print(categoryId)
                    print(data.stock)
                    df = strategy80_running(stock=data.stock, source=data.source, 
                    categoryId=categoryId,timing=data.timing, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,backtest=0) # perfect
                    check_signal(df,data.timing,data.stock,1,categoryId,"notes",1,1,0)
                    supertrend2db_running(df,data.timing)
                    # graphviewpositive(data.stock, df)
            else:
                print("USA Market Closed")

        if categoryId == 3 or categoryId == 4 or categoryId == 5:
            portfolioInstance = stockdata.objects.filter(portfolioId=categoryId)
            sgttime = dt.utcnow() + timedelta(hours=8)
            day = sgttime.weekday()
            sgttime = sgttime.time()
            if day < 7 and is_time_between(time(6, 00), time(4, 00), sgttime):
                print("SGT Market Hours is working" + str(sgttime))
                sgtmarkets = 1
                for data in portfolioInstance:
                    print(categoryId)
                    print(data.stock)
                    df = strategy80_running(stock=data.stock, source=data.source, 
                    categoryId=categoryId,timing=data.timing, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,backtest=0) # perfect
                    check_signal(df,data.timing,data.stock,1,categoryId,"notes",1,1,0)
                    supertrend2db_running(df,data.timing)
                    # graphviewpositive(data.stock, df)
            else:
                print("Global Markets are closed")

        if (categoryId == 6 or categoryId == 8 or categoryId == 11 ):
            portfolioInstance = stockdata.objects.filter(portfolioId=categoryId)
            isttime = dt.utcnow() + timedelta(hours=5.5)
            day = isttime.weekday()
            isttime = isttime.time()
            if day < 6 and is_time_between(time(9, 15), time(17, 30), isttime):
                print("IST Market Hours is working" + str(isttime))
                for data in portfolioInstance:
                    print(categoryId)
                    print(data.stock)
                    # if data.stock=='TQQQ':
                    df = strategy80_running(stock=data.stock, source=data.source, 
                    categoryId=categoryId,timing=data.timing, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,backtest=0) # perfect
                    check_signal(df,data.timing,data.stock,1,categoryId,"notes",1,1,0)
                    supertrend2db_running(df,data.timing)
                    # graphviewpositive(data.stock, df)
            else:
                print("IST Market Closed")

        if categoryId == 7:
            portfolioInstance = stockdata.objects.filter(portfolioId=categoryId)
            for data in portfolioInstance:   
                print(categoryId)
                print(data.stock)
                df = strategy80_running(stock=data.stock, source=data.source, 
                categoryId=categoryId,timing=data.timing, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,backtest=0) # perfect
                check_signal(df,data.timing,data.stock,1,categoryId,"notes",1,1,0)
                supertrend2db_running(df,data.timing)
                # graphviewpositive(data.stock, df)

    i = i+1

    stoptime = dt.utcnow() + timedelta(hours=8)
    duration = stoptime - starttime
    print(stoptime)
    print(duration)
    message = "task completed."
    return message



@shared_task()
def scripttask():
   
    # df = strategy80_running("NIFTY", "NSE", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.01,meantrade=1,pos=1.01,neg=0.995) # good.
    df = strategy80_running("NAS100USD", "OANDA", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.01,meantrade=1)
    # df = strategy80_running("SPX500USD", "OANDA", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.01,meantrade=1,pos=1.001,neg=0.99)
    # df = strategy80_running("TITAN", "NSE", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.01,meantrade=1,pos=1.010,neg=0.90)
    # df = strategy80_running("BAJFINANCE", "NSE", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.01,meantrade=0.7)
    # df = strategy80_running("SOXL", "AMEX", 1,timing=3, atr_period=18, multiplier=3,tradetype=0,minloss=0.99,minprofit=1.05,meantrade=1.1)
    # df = strategy80_running("AAPL", "NASDAQ", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1.2,pos=1.04,neg=0.98)
    # df = strategy80_running("NAS100USD", "OANDA", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1.2,pos=1.04,neg=0.98)
    # df = strategy80_running("NEOUSD", "BITFINEX", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1.2,pos=1.10,neg=0.95)
    # df = strategy80_running("GOLD", "TVC", 1,timing=5, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,pos=1.01,neg=0.99) # perfect
    # df = strategy80_running("BTCUSD", "COINBASE", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,pos=1.001,neg=0.99)
    # df = strategy80_running("EURUSD", "OANDA", 1,timing=3, atr_period=18, multiplier=3,tradetype=1,minloss=0.99,minprofit=1.05,meantrade=1,pos=1.001,neg=0.99)
    # graphviewpositive("NEOUSD",df)
@shared_task()
def strategy2_running(stock,myportfolio_id,df, categoryId,debug,minloss,minprofit,pos,neg,tradetype=0,backtest=0):
    
    df["meanvol"] = df["volume"].rolling(50).mean()
    _position = stock + "_position"
    _trade = stock + "_trade"
    _selltrade = stock + "_selltrade"
    _trend = stock + "_trend"

   
    if backtest == 1:
        localStorage.setItem(_position,1)
        localStorage.setItem(_trade,0)


    _profitbuy = 0
    _loss = 0

    _sell = oldsell = df["close"].max()
    _buy = 0
    winrate = 0
    lossrate = 0
    totaltrades = 0
    totalprofit = 0
    tag = 0
    _pointer = 0

    _buyclose = 0
    _sellclose = 0
    _iposition = 0
    _fposition = 0
    _ploss = 0
    _pprofit = 0
    _lprofit = 0
    ploss = 0
    lloss = 0
    buy = 0
    sell = 0
    secondposition = 0
    position1loss = 0
    position = 1


    for i, row in df.iterrows():
        prev1, prev2, prev3 = i - 1, i - 2, i - 3
        
      
        if position == 1:
            # ic(i,position)
            if float(df.loc[i, "trend"]) == 1 :
                if float(df.loc[prev1, "tsuperbuy"]) > 0 or float(df.loc[prev2, "tsuperbuy"]) > 0 or float(df.loc[prev2, "tsuperbuy"]) > 0:
                    
                    buy = df.loc[i, "buy"] = df.loc[i, "close"]
                    notes = df.loc[i, "notes"] = "1Trendbuy - Tsuperbuy"
                    ploss = 0
                    position = df.loc[i, "position"] = 2
                    trend = df.loc[i, "trend"] 
                    superbuy = df.loc[i, "buy"] = df.loc[i, "close"]
                    zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3,zone2 = 0,0,0,0,0,0,0,0,0
                    upperpoint = buy * pos 
                    lowerpoint = buy * neg
                    distance_lowerpoint = buy - lowerpoint
                    distance_upperpoint = upperpoint - buy
                    df.loc[i, "upperpoint"] = round(upperpoint,4)
                    df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                    df.loc[i, "s5underbuy"] = s5underbuy = round(buy - distance_lowerpoint * 0.5,4)
                    df.loc[i, "s3underbuy"] = s3underbuy = round(buy - distance_lowerpoint * 0.236,4)
                    df.loc[i, "p2superbuy"] = p2superbuy = round(buy + distance_upperpoint * 0.236,4)
                    df.loc[i, "p3superbuy"] = p3superbuy = round(buy + distance_upperpoint * 0.382,4)
                    df.loc[i, "p5superbuy"] = p5superbuy = round(buy + distance_upperpoint * 0.500,4)
                    df.loc[i, "p6superbuy"] = p6superbuy = round(buy + distance_upperpoint * 0.618,4)
                    df.loc[i, "p7superbuy"] = p7superbuy =  round(buy + distance_upperpoint * 0.786,4)
                    df.loc[i, "p10superbuy"] = p10superbuy = round(buy + distance_upperpoint * 1,4)
                    df.loc[i, "p12superbuy"] = p12superbuy = round(buy + distance_upperpoint * 1.23,4)
                    df.loc[i, "p13superbuy"] = p13superbuy = round(buy + distance_upperpoint * 1.382,4)
                    df.loc[i, "p16superbuy"] = p16superbuy = round(buy + distance_upperpoint * 1.618,4)
                    df.loc[i, "p20superbuy"] = p20superbuy = round(buy + distance_upperpoint * 2.0,4)
                    _sposition = i
                    if backtest:
                        send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                    if debug:
                        # ic(i,buy,upperpoint,lowerpoint,distance_lowerpoint,distance_upperpoint,s5underbuy,s3underbuy,p2superbuy,p3superbuy,p5superbuy,p6superbuy,p7superbuy,
                        # p10superbuy,p12superbuy,p13superbuy,p20superbuy)
                        print(i,trend,notes,buy,_pprofit)

                elif i > _iposition + 6 and _ploss < 2 :
                    
                    if _buyclose < float(df.loc[i, "close"]):
                        buy = df.loc[i, "buy"] = df.loc[i, "close"]
                        _buy = buy
                        notes = df.loc[i, "notes"] = "1Trendbuy - Second Buy "
                        ploss = 0
                        position = df.loc[i, "position"] = 2
                        trend = df.loc[i, "trend"] 
                        superbuy = df.loc[i, "buy"] = df.loc[i, "close"]
                        zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3,zone2 = 0,0,0,0,0,0,0,0,0
                        upperpoint = buy * pos 
                        lowerpoint = buy * neg
                        distance_lowerpoint = buy - lowerpoint
                        distance_upperpoint = upperpoint - buy
                        df.loc[i, "upperpoint"] = round(upperpoint,4)
                        df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                        df.loc[i, "s5underbuy"] = s5underbuy = buy - distance_lowerpoint * 0.5
                        df.loc[i, "s3underbuy"] = s3underbuy = buy - distance_lowerpoint * 0.236
                        df.loc[i, "p2superbuy"] = p2superbuy = round(buy + distance_upperpoint * 0.236,4)
                        df.loc[i, "p3superbuy"] = p3superbuy = round(buy + distance_upperpoint * 0.382,4)
                        df.loc[i, "p5superbuy"] = p5superbuy = round(buy + distance_upperpoint * 0.500,4)
                        df.loc[i, "p6superbuy"] = p6superbuy = round(buy + distance_upperpoint * 0.618,4)
                        df.loc[i, "p7superbuy"] = p7superbuy =  round(buy + distance_upperpoint * 0.786,4)
                        df.loc[i, "p10superbuy"] = p10superbuy = round(buy + distance_upperpoint * 1,4)
                        df.loc[i, "p12superbuy"] = p12superbuy = round(buy + distance_upperpoint * 1.236,4)
                        df.loc[i, "p13superbuy"] = p13superbuy = round(buy + distance_upperpoint * 1.382,4)
                        df.loc[i, "p16superbuy"] = p16superbuy = round(buy + distance_upperpoint * 1.618,4)
                        df.loc[i, "p20superbuy"] = p20superbuy = round(buy + distance_upperpoint * 2.0,4)
                        _sposition = i
                        if backtest:
                            send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                        if debug:
                            # ic(i,buy,upperpoint,lowerpoint,distance_lowerpoint,distance_upperpoint,s5underbuy,s3underbuy,p2superbuy,p3superbuy,p5superbuy,p6superbuy,p7superbuy,
                            # p10superbuy,p12superbuy,p13superbuy,p20superbuy)
                            print(i,trend,notes,buy,_pprofit)

            
            if float(df.loc[i, "trend"]) == 2 :
                if float(df.loc[prev1, "tsupersell"]) > 0 or float(df.loc[prev2, "tsupersell"]) > 0 or float(df.loc[prev2, "tsupersell"]) > 0:
                    ic('supersell',i,position)
                    # if _sell > float(df.loc[prev1, "supersell"]):
                    sell = df.loc[i, "sell"] = df.loc[i, "close"]
                    notes = df.loc[i, "notes"] = "1TrendSell - TSupersell"
                    ploss = 0
                    position = df.loc[i, "position"] = 3
                    trend = df.loc[i, "trend"] 
                    lowerpoint = sell * neg
                    upperpoint = sell * pos 
                    distance_lowerpoint = upperpoint - sell
                    distance_upperpoint = sell - lowerpoint 
                    
                    zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3 = 0,0,0,0,0,0,0,0
                    df.loc[i, "upperpoint"] = round(upperpoint,4)
                    df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                    df.loc[i, "s5undersell"] = s5undersell = round(sell + distance_upperpoint * 0.7,4)
                    df.loc[i, "s3undersell"] = s3undersell = round(sell + distance_upperpoint * 0.236,4)
                    df.loc[i, "p2supersell"] = p2supersell = round(sell - distance_lowerpoint * 0.236,4)
                    df.loc[i, "p3supersell"] = p3supersell = round(sell - distance_lowerpoint * 0.382,4)
                    df.loc[i, "p5supersell"] = p5supersell = round(sell - distance_lowerpoint * 0.500,4)
                    df.loc[i, "p6supersell"] = p6supersell = round(sell - distance_lowerpoint * 0.618,4)
                    df.loc[i, "p7supersell"] = p7supersell =  round(sell - distance_lowerpoint * 0.786,4)
                    df.loc[i, "p10supersell"] = p10supersell = round(sell - distance_lowerpoint * 1,4)
                    df.loc[i, "p12supersell"] = p12supersell = round(sell - distance_lowerpoint * 1.236,4)
                    df.loc[i, "p13supersell"] = p13supersell = round(sell - distance_lowerpoint * 1.382,4)
                    df.loc[i, "p16supersell"] = p16supersell = round(sell - distance_lowerpoint * 1.618,4)
                    df.loc[i, "p20supersell"] = p20supersell = round(sell - distance_lowerpoint * 2.0,4)
                    _iposition = i
                    secondposition = 0
                    if backtest:
                        send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                    if debug:
                        # ic(i,sell,pos,upperpoint,neg,lowerpoint,distance_lowerpoint,distance_upperpoint,s5undersell,s3undersell,p2supersell,p3supersell,p5supersell,p6supersell,p7supersell,
                        # p10supersell,p12supersell,p13supersell,p16supersell,p20supersell,_lprofit)
                        print(i,trend,sell,notes,_lprofit)
            
            
            if float(df.loc[i, "trend"]) == 2 :
                if float(df.loc[i, "ssupersell"]) > 0  or float(df.loc[prev1, "ssupersell"]) > 2:
                    ic('supersell',i,position)
                    # if _sell > float(df.loc[prev1, "supersell"]):
                    sell = df.loc[i, "sell"] = df.loc[i, "close"]
                    notes = df.loc[i, "notes"] = "1Trend2- 2nd Type Sell"
                    ploss = 0
                    position = df.loc[i, "position"] = 3
                    trend = df.loc[i, "trend"] 
                    lowerpoint = sell * neg
                    upperpoint = sell * pos 
                    distance_lowerpoint = upperpoint - sell
                    distance_upperpoint = sell - lowerpoint 
                    
                    zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3 = 0,0,0,0,0,0,0,0
                    df.loc[i, "upperpoint"] = round(upperpoint,4)
                    df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                    df.loc[i, "s5undersell"] = s5undersell = round(sell + distance_upperpoint * 0.7,4)
                    df.loc[i, "s3undersell"] = s3undersell = round(sell + distance_upperpoint * 0.236,4)
                    df.loc[i, "p2supersell"] = p2supersell = round(sell - distance_lowerpoint * 0.236,4)
                    df.loc[i, "p3supersell"] = p3supersell = round(sell - distance_lowerpoint * 0.382,4)
                    df.loc[i, "p5supersell"] = p5supersell = round(sell - distance_lowerpoint * 0.500,4)
                    df.loc[i, "p6supersell"] = p6supersell = round(sell - distance_lowerpoint * 0.618,4)
                    df.loc[i, "p7supersell"] = p7supersell =  round(sell - distance_lowerpoint * 0.786,4)
                    df.loc[i, "p10supersell"] = p10supersell = round(sell - distance_lowerpoint * 1,4)
                    df.loc[i, "p12supersell"] = p12supersell = round(sell - distance_lowerpoint * 1.236,4)
                    df.loc[i, "p13supersell"] = p13supersell = round(sell - distance_lowerpoint * 1.382,4)
                    df.loc[i, "p16supersell"] = p16supersell = round(sell - distance_lowerpoint * 1.618,4)
                    df.loc[i, "p20supersell"] = p20supersell = round(sell - distance_lowerpoint * 2.0,4)
                    _iposition = i
                    secondposition = 0
                    if backtest:
                        send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                    if debug:
                        # ic(i,sell,pos,upperpoint,neg,lowerpoint,distance_lowerpoint,distance_upperpoint,s5undersell,s3undersell,p2supersell,p3supersell,p5supersell,p6supersell,p7supersell,
                        # p10supersell,p12supersell,p13supersell,p16supersell,p20supersell,_lprofit)
                        print(i,trend,sell,notes,_lprofit)


            elif df.loc[i, "trend"] == 2  :
                # ic('supersell1',i,position)
                if _sellclose > float(df.loc[i, "close"]):
                    sell = df.loc[i, "sell"] = df.loc[i, "close"]
                    notes = df.loc[i, "notes"] = "1TrendSell - Type 3 Entry"
                    ploss = 0
                    position = df.loc[i, "position"] = 3
                    trend = df.loc[i, "trend"] 
                    zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3 = 0,0,0,0,0,0,0,0

                    lowerpoint = sell * neg
                    upperpoint = sell * pos 
                    distance_lowerpoint = sell - lowerpoint
                    distance_upperpoint = upperpoint - sell
                    df.loc[i, "upperpoint"] = round(upperpoint,4)
                    df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                    df.loc[i, "s5undersell"] = s5undersell = round(sell + distance_upperpoint * 0.5,4)
                    df.loc[i, "s3undersell"] = s3undersell = round(sell + distance_upperpoint * 0.236,4)
                    df.loc[i, "p2supersell"] = p2supersell = round(sell - distance_lowerpoint * 0.236,4)
                    df.loc[i, "p3supersell"] = p3supersell = round(sell - distance_lowerpoint * 0.382,4)
                    df.loc[i, "p5supersell"] = p5supersell = round(sell - distance_lowerpoint * 0.500,4)
                    df.loc[i, "p6supersell"] = p6supersell = round(sell - distance_lowerpoint * 0.618,4)
                    df.loc[i, "p7supersell"] = p7supersell =  round(sell - distance_lowerpoint * 0.786,4)
                    df.loc[i, "p10supersell"] = p10supersell = round(sell - distance_lowerpoint * 1,4)
                    df.loc[i, "p12supersell"] = p12supersell = round(sell - distance_lowerpoint * 1.236,4)
                    df.loc[i, "p13supersell"] = p13supersell = round(sell - distance_lowerpoint * 1.382,4)
                    df.loc[i, "p16supersell"] = p16supersell = round(sell - distance_lowerpoint * 1.618,4)
                    df.loc[i, "p20supersell"] = p20supersell = round(sell - distance_lowerpoint * 2.0,4)
                    if backtest:
                        send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)

                    if debug:
                        # ic(i,sell,upperpoint,lowerpoint,distance_lowerpoint,distance_upperpoint,s5undersell,s3undersell,p2supersell,p3supersell,p5supersell,p6supersell,p7supersell,
                        # p10supersell,p12supersell,p13supersell,p16supersell,p20supersell,_lprofit)
                        print(i,trend,notes,sell,_lprofit)

            elif df.loc[i, "trend"] == 2 and position1loss == 1 :
                # ic('supersell1',i,position)
                
                sell = df.loc[i, "sell"] = df.loc[i, "close"]
                notes = df.loc[i, "notes"] = "1TrendSell - Type 4 Entry"
                ploss = 0
                position = df.loc[i, "position"] = 3
                trend = df.loc[i, "trend"] 
                zone20,zone16,zone13,zone12,zone10,zone7,zone6,zone3 = 0,0,0,0,0,0,0,0

                lowerpoint = sell * neg
                upperpoint = sell * pos 
                distance_lowerpoint = sell - lowerpoint
                distance_upperpoint = upperpoint - sell
                df.loc[i, "upperpoint"] = round(upperpoint,4)
                df.loc[i, "lowerpoint"] = round(lowerpoint,4)
                df.loc[i, "s5undersell"] = s5undersell = round(sell + distance_upperpoint * 0.5,4)
                df.loc[i, "s3undersell"] = s3undersell = round(sell + distance_upperpoint * 0.236,4)
                df.loc[i, "p2supersell"] = p2supersell = round(sell - distance_lowerpoint * 0.236,4)
                df.loc[i, "p3supersell"] = p3supersell = round(sell - distance_lowerpoint * 0.382,4)
                df.loc[i, "p5supersell"] = p5supersell = round(sell - distance_lowerpoint * 0.500,4)
                df.loc[i, "p6supersell"] = p6supersell = round(sell - distance_lowerpoint * 0.618,4)
                df.loc[i, "p7supersell"] = p7supersell =  round(sell - distance_lowerpoint * 0.786,4)
                df.loc[i, "p10supersell"] = p10supersell = round(sell - distance_lowerpoint * 1,4)
                df.loc[i, "p12supersell"] = p12supersell = round(sell - distance_lowerpoint * 1.236,4)
                df.loc[i, "p13supersell"] = p13supersell = round(sell - distance_lowerpoint * 1.382,4)
                df.loc[i, "p16supersell"] = p16supersell = round(sell - distance_lowerpoint * 1.618,4)
                df.loc[i, "p20supersell"] = p20supersell = round(sell - distance_lowerpoint * 2.0,4)
                if backtest:
                    send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)

                if debug:
                    # ic(i,sell,upperpoint,lowerpoint,distance_lowerpoint,distance_upperpoint,s5undersell,s3undersell,p2supersell,p3supersell,p5supersell,p6supersell,p7supersell,
                    # p10supersell,p12supersell,p13supersell,p16supersell,p20supersell,_lprofit)
                    print(i,trend,notes,sell,_lprofit)

        elif position == 2:
            # print(i,trend,float(df.loc[i, "close"]))
            notes = df.loc[i, "notes"] = "S2 - TSupersell Triggered. " 
            if i > _sposition + 3:
                    if float(df.loc[i, "close"]) > p20superbuy:
                        zone20 = 1
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-zone10 - superbuy"  
                        distance = round(float(df.loc[i, "close"]) - buy,2)
                        # print(i,trend,"p20.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p20superbuy,notes)


                    elif float(df.loc[i, "close"]) > p16superbuy:
                        zone16 = 1
                        notes = df.loc[i, "notes"] = "S2-zone16 - superbuy"  
                        distance = round(float(df.loc[i, "close"]) - buy,2)
                        # print(i,trend,"p16.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p16superbuy,notes)
                
                    elif float(df.loc[i, "close"]) > p13superbuy:
                        if zone16 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone16 triggered."  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p13.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p13superbuy,notes)
                        else:
                            zone13 = 1
                            notes = df.loc[i, "notes"] = "S2-zone13 - superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p13.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p13superbuy,notes)
                    
                    elif float(df.loc[i, "close"]) > p12superbuy:
                        if zone13 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone13 triggered."  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p12.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p12superbuy,notes)
                    
                        else:
                            zone12 = 1
                            notes = df.loc[i, "notes"] = "S2-zone12 - superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p12.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p13superbuy,notes)
                    elif float(df.loc[i, "close"]) > p10superbuy:
                        if zone12 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] =  "zone12 triggered."  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p10.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p10superbuy,notes)
                    
                        else:
                            zone10 = 1
                            notes = df.loc[i, "notes"] = "S2-zone10 - superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p10.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p10superbuy,notes)
                    
                    elif float(df.loc[i, "close"]) > p7superbuy:
                        if zone10 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone10 triggered."  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p7.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p7superbuy,notes)
                        else:
                            zone7 = 1
                            notes = df.loc[i, "notes"] = "S2-zone7 - superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p7.....",zone7,"buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p7superbuy,notes)
                
                    elif float(df.loc[i, "close"]) > p6superbuy:
                        if zone7 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone7 triggered."  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p6.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p6superbuy,notes)
                        else:
                            zone6 = 1
                            notes = df.loc[i, "notes"] = "S2-zone6 - superbuy"    
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p6.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p6superbuy,notes)
                        
                    elif float(df.loc[i, "close"]) > p5superbuy: 
                        if zone6 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone6 triggered." 
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p3.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p3superbuy,notes)
                        else:
                            zone5 = 1
                            notes = df.loc[i, "notes"] = "S2-zone3 - superbuy"    
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p3.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p3superbuy,notes)
                    
                    # elif float(df.loc[i, "close"]) > p2superbuy: 
                    #     if zone3 == 1:
                    #         ploss = 1
                    #         notes = df.loc[i, "notes"] = "zone3 triggered." 
                    #         distance = round(float(df.loc[i, "close"]) - buy,2)
                    #     #     print(i,trend,"p3.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p3superbuy,notes)
                    #     # else:
                    #         zone2 = 1
                    #         notes = df.loc[i, "notes"] = "S2-zone2 - superbuy"    
                    #         distance = round(float(df.loc[i, "close"]) - buy,2)
                    #         print(i,trend,"p2superbuy.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",p3superbuy,notes)
                    #         print(i,zone2)
                    elif float(df.loc[i, "close"]) > superbuy: 
                        if zone2 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone3 triggered." 
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            print(i,trend,"p2 superbuy hit.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",superbuy,notes)
                        else:
                            notes = df.loc[i, "notes"] = "S2-zone1 superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p1 floating here.","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",superbuy,notes)

                   
                    
                    elif float(df.loc[i, "close"]) < superbuy: 
                        if zone2 == 1:
                            ploss = 1
                            notes = df.loc[i, "notes"] = "zone2 triggered." 
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"zone2.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",superbuy,notes)
                        else:
                            notes = df.loc[i, "notes"] = "S2-zone 0 underwater - superbuy"  
                            distance = round(float(df.loc[i, "close"]) - buy,2)
                            # print(i,trend,"p1.....","buy--->",buy,"close--->",float(df.loc[i, "close"]),distance,"stop-loss-target->",s5underbuy,notes)

                    if float(df.loc[i, "close"]) < lowerpoint:
                        zone0 = 1
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-Stoploss - Closebuy"  
                        distance = round(float(df.loc[i, "close"]) - buy,2)
                        # print(i,trend,"p0.....","buy--->",buy,float(df.loc[i, "close"]),distance,"target->",superbuy,notes)
                    


            if  ploss == 1 or float(df.loc[i, "tsupersell"]) > 0  :
                # if float(df.loc[i, "close"]) < ploss:
                buyclose = df.loc[i, "buyclose"] = df.loc[i, "close"]
                profitloss = buyclose - buy
                # let's draw the fibbonacci
                _buy = buy
                _buyclose = buyclose
                _iposition = i
                
                position = df.loc[i, "position"] = 1
                superbuy = 0
                totalprofit = totalprofit + profitloss
                totaltrades = totaltrades + 1
                ploss = 0
                if profitloss >= 0:
                    winrate = winrate + 1 
                    _ploss = 0
                    _pprofit = _pprofit + 1
                    _lprofit = 0
                    winpercentage = winrate/totaltrades * 100
                else:
                    lossrate = lossrate + 1
                    position1loss = 1
                    
                if backtest:
                    send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                if debug:
                    winpercentage = winrate/totaltrades * 100
                    print(i,trend,position,notes,buy,_buyclose,profitloss,totaltrades,winrate,lossrate,_loss,totalprofit,winpercentage)


        
        
            
                
        elif position == 3:
          
            if i > _iposition + 6:
                
                notes = df.loc[i, "notes"] = "S2- TSuperbuy Hit."  
                
                if float(df.loc[i, "close"]) < p20supersell:
                    zone20 = 1
                    ploss = 1
                    notes = df.loc[i, "notes"] = "S2-S20 supersell"  
                    distance = round(sell - float(df.loc[i, "close"]),2)
                    # print(i,trend,"p20.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p20supersell,notes)

                elif float(df.loc[i, "close"]) < p16supersell:
                    if zone20 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S20 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                    #     print(i,trend,"p20.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p16supersell,notes)
                    else:
                        zone16 = 1
                        notes = df.loc[i, "notes"] = "S2-S16 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"p16.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p16supersell,notes)

                elif float(df.loc[i, "close"]) < p12supersell:
                    if zone16 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S16 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                    #     print(i,trend,"p16.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p12supersell,notes)
                    else:
                        zone12 = 1
                        notes = df.loc[i, "notes"] = "S2-S12 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                #         print(i,trend,"p12.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p12supersell,notes)
                elif float(df.loc[i, "close"]) < p10supersell:
                    if zone12 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S12 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                    #     print(i,trend,"p12.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p12supersell,notes)
                    else:
                        zone10 = 1
                        notes = df.loc[i, "notes"] = "S2-S10 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        print(i,trend,"p10.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p10supersell,notes)

                elif float(df.loc[i, "close"]) < p7supersell:
                    if zone10 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S10 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"p10.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p7supersell,notes)

                    else:
                        zone7 = 1
                        notes = df.loc[i, "notes"] = "S2-S7 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"p7.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p7supersell,notes)


                elif float(df.loc[i, "close"]) < p6supersell:
                    if zone7 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S7 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"p7.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p6supersell,notes)

                    else:
                        zone6 = 1
                        notes = df.loc[i, "notes"] = "S2-S6 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"p6.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p6supersell,notes)

                    
                elif float(df.loc[i, "close"]) < p3supersell: 
                    if zone6 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S6 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"P6.....","sell--->",sell,"iclose--->",float(df.loc[i, "close"]),distance,"target->",p3supersell,notes)

                    else:
                        zone3 = 1
                        notes = df.loc[i, "notes"] = "S2-S3 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"P3.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",p3supersell,notes)

                elif float(df.loc[i, "close"]) < sell: 
                    if zone6 == 1:
                        ploss = 1
                        notes = df.loc[i, "notes"] = "S2-S3 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"S0.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",sell,notes)

                    else:
                        notes = df.loc[i, "notes"] = "S2-S0 Supersell"  
                        distance = round(sell - float(df.loc[i, "close"]),2)
                        # print(i,trend,"S0.....","sell--->",sell,float(df.loc[i, "close"]),distance,"target->",supersell,notes)

                elif float(df.loc[i, "close"]) > s5undersell  :
                    zone0 = 1
                    ploss = 1
                    notes = df.loc[i, "notes"] = "S2-Stoploss Sell"  
                    distance = round(sell - float(df.loc[i, "close"]),2)
                    print("-----------------------------------------------------------------------------")
                    print(i,notes)
                    print(i,trend,"p0.....","sell--->",sell,float(df.loc[i, "close"]),distance,"crossed",s5undersell,notes)
                    
                

                if ploss == 1  or float(df.loc[i, "tsuperbuy"]) :
                    trend = df.loc[i, "trend"]
                    sellclose = df.loc[i, "sellclose"] = df.loc[i, "close"]
                    profitloss =  sell - sellclose
                    _sell = sell
                    _sellclose = sellclose
                    _fposition = i
                    if profitloss > 0:
                        winrate = winrate + 1
                        _lprofit = _lprofit + 1
                        _pprofit = 0
                        secondposition = 1
                    else:
                        lossrate = lossrate + 1
                    position = df.loc[i, "position"] = 1
                    if backtest:
                        send_signal(df,i, stock,myportfolio_id, categoryId, notes,0,0,1)
                    totalprofit = totalprofit + profitloss
                    totaltrades = totaltrades + 1
                    supersell = 0
                    ploss = 0
                    if debug:
                        winpercentage = winrate/totaltrades * 100
                        ic(i,trend,notes,position,_sell,_sellclose,profitloss,p16supersell,totaltrades,winrate,_loss,totalprofit,winpercentage,s3undersell)

        
    
    df.reset_index(inplace=True)
    df = df.replace([0],np.nan)
    return df



@shared_task()
def check_signal(df,timing,stock,myportfolio_id,categoryId,notes,istelegram,islive,backtesting):
    print("check_signal")
    
    size = len(df.index)
    loopsize = 3
    if timing == 1:
        loopsize = 3
    if timing == 3:
        loopsize = 1
    if timing == 5:
        loopsize = 5

    for r in range(loopsize,0,-1):
       
        i = size - r
        print("checksignal",i)
        send_running_signal(df, i,stock,myportfolio_id, categoryId,notes,istelegram,islive,backtesting)

    return df



@shared_task()
def send_signal(df, i,stock,myportfolio_id, categoryId,notes,istelegram,islive,backtesting):


    
    _trade = stock + "_trade"
    _position = stock + "_position"
    _stockprice = stock + "_stockprice"
    _stocktime = stock + "_stocktime"

    
    _buystoploss = stock + "_buystoploss"
    _buytp1 = stock + "_buytp1"
    _buytp2 = stock + "_buytp2"
    _buytp3 = stock + "_buytp3"
    _sellstoploss = stock + "_sellstoploss"
    _selltp1 = stock + "_selltp1"
    _selltp2 = stock + "_selltp2"
    _selltp3 = stock + "_selltp3"

    position = localStorage.getItem(_position)
    trade = localStorage.getItem(_trade)
    stockprice = localStorage.getItem(_stockprice)
    stocktime = localStorage.getItem(_stocktime)


    if position is None:
        position = 1
    if trade is None:
        trade = 0
    if stockprice is None:
        stockprice = 0
    if stocktime is None:
        stocktime = 0


    position = int(position)
    trade = int(trade)
   
   
    try:
        buy = df.loc[i,"buy"] 
    except:
        df["buy"] = 0
    try:
        buyclose = df.loc[i,"buyclose"] 
    except:
        df["buyclose"] = 0
    try:
        sell = df.loc[i,"sell"] 
    except:
        df["sell"] = 0
    try:
        sellclose = df.loc[i,"sellclose"] 
    except:
        df["sellclose"] = 0

    #### chat_id = -1001763597956

    if df.loc[i,"buy"] > 0:
        
        
        if position == 1 and trade == 0:
            signal = "BUY"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(pytz.utc)
            message = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>BUY </b>"
                + "<b>" + str(df.loc[i,"buy"])+ "</b>" + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Upperpoint "
                + str(df.loc[i,"upperpoint"]) + "\n "
                + "Lowerpoint "
                + str(df.loc[i,"lowerpoint"]) + "\n "
                + "Stoploss "
                + str(df.loc[i,"s5underbuy"]) + "\n "
                + "TP1 "
                + str(df.loc[i,"p5superbuy"]) + "\n "
                + "TP2 "
                + str(df.loc[i,"p10superbuy"]) + "\n "
                + "TP3 "   
                + str(df.loc[i,"p20superbuy"]) + "\n "
            )
            localStorage.setItem(_buystoploss,df.loc[i,"s5underbuy"] )
            localStorage.setItem(_buytp1, df.loc[i,"p5superbuy"] )
            localStorage.setItem(_buytp2, df.loc[i,"p7superbuy"] )
            localStorage.setItem(_buytp3, df.loc[i,"p10superbuy"] )
            # send_telegram_signal("param", debugmessage,"-1001763597956")
        
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df["datetime"].iloc[i]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df["notes"].iloc[i]
            data["analysis"] = i
           
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)

            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
                
            position = 2
            trade = 1
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
            localStorage.setItem(_stockprice, close)
            localStorage.setItem(_stocktime, df["datetime"].iloc[i])
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", message,chat_id)
                if stock == "GOLD":
                    send_telegram_signal("param", message, chat_id)

    elif df.loc[i,"buyclose"] > 0:

       
        if position == 2 and trade == 1:
            msg = ""
            buystoploss = localStorage.getItem(_buystoploss )
            buytp1 = localStorage.getItem(_buytp1 )
            buytp2 =  localStorage.getItem(_buytp2 )
            buytp3 = localStorage.getItem(_buytp3 )
            buyclose = str(df.loc[i,"buyclose"])

            if buyclose > buytp3:
                # ic(buyclose,buytp3)
              
                msg = "TP3 Triggered"
            elif buytp2 < buyclose < buytp3:
                # ic(buytp2,buyclose,buytp3)
             
                msg = "TP2 Triggered"
            elif buytp1 < buyclose  < buytp2:
                # ic(buytp1,buyclose,buytp2)
            
                msg = "TP1 Triggered"
            elif buyclose < buystoploss:
                # ic(buyclose,buystoploss)
             
                msg = "Stoploss Triggered"

            
            starttime = localStorage.getItem(_stocktime)
            signal = "BUYCLOSE"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(
                pytz.utc
            )
            stockprice = localStorage.getItem(_stockprice) 
            profitloss = close - float(stockprice)
            starttime = dt.fromisoformat(str(starttime)).astimezone(pytz.utc)
            duration = str(signaldate - starttime)
            profitloss = round(profitloss,2)
            if profitloss > 0:
                profitstring = '<b>' + str(profitloss) + '</b>'
            else:
                profitstring = '<b>' + str(profitloss) + '</b>'

            message = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>BUYCLOSE </b>"
                + "<b>" + str(df.loc[i,"buyclose"])+ "</b>" + "\n "
                + " "
                + str(msg) + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
            )
            # send_telegram_signal("param", debugmessage,"-1001763597956")
         
            
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df.loc[i,"datetime"]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df.loc[i,"notes"]
            data["profitloss"] = profitloss
            data["duration"] = duration
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                ic(serializer.errors)

            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
             
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
   
            position = 1
            trade = 0
            localStorage.setItem(_position, position) 
            localStorage.setItem(_trade, trade) 
           ### chat_id = -1001763597956
            if istelegram:
                    send_telegram_signal("param", message,chat_id)
                    if stock == "GOLD":
                        send_telegram_signal("param", message, chat_id)
    elif df.loc[i,"sell"] > 0:
        if position == 1 and trade == 0:
            message = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>SELL </b>"
                + "<b>" + str(df.loc[i,"sell"])+ "</b>" + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Upperpoint "
                + str(df.loc[i,"upperpoint"]) + "\n "
                + "Lowerpoint "
                + str(df.loc[i,"lowerpoint"]) + "\n "
                + "Stoploss "
                + str(df.loc[i,"s3undersell"]) + "\n "
                + "TP1 "
                + str(df.loc[i,"p5supersell"]) + "\n "
                + "TP2 "
                + str(df.loc[i,"p10supersell"]) + "\n "
                + "TP3 "   
                + str(df.loc[i,"p20supersell"]) + "\n "
            )

            localStorage.setItem(_sellstoploss,df.loc[i,"s5undersell"] )
            localStorage.setItem(_selltp1, df.loc[i,"p5supersell"] )
            localStorage.setItem(_selltp2, df.loc[i,"p10supersell"] )
            localStorage.setItem(_selltp3, df.loc[i,"p20supersell"] )
            # send_telegram_signal("param", debugmessage,"-1001763597956")

            signal = "SELL"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(pytz.utc)
            
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df["datetime"].iloc[i]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df["notes"].iloc[i]
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)
            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
           
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
        

            position = 3
            trade = 1
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
            localStorage.setItem(_stockprice, close)
            localStorage.setItem(_stocktime, df["datetime"].iloc[i])
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", message,chat_id)
                if stock == "GOLD":
                    send_telegram_signal("param", message, chat_id)
    elif df.loc[i,"sellclose"] > 0:
        if position == 3 and trade == 1:
            
           
            signal = "SELLCLOSE"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(
                pytz.utc
            )
            stockprice = localStorage.getItem(_stockprice) 
            profitloss =  float(stockprice) - close 
            starttime = localStorage.getItem(_stocktime)
            starttime = dt.fromisoformat(str(starttime)).astimezone(pytz.utc)
            duration = str(signaldate - starttime)
            profitloss = round(profitloss,2)
            if profitloss > 0:  
                profitstring = '<b style="color:green">' + str(profitloss) + '</b>'
            else:
                profitstring = '<b style="color:red">' + str(profitloss) + '</b>'

        

            msg = ""
            sellstoploss = float(localStorage.getItem(_sellstoploss ))
            selltp1 = float(localStorage.getItem(_selltp1 ))
            selltp2 =  float(localStorage.getItem(_selltp2 ))
            selltp3 =  float(localStorage.getItem(_selltp3 ))
            sellclose = float(df.loc[i,"sellclose"])
            ic(sellclose,selltp1,selltp2,selltp3)

            if sellclose < float(selltp3):
             
                msg = "TP3 Triggered"
            elif selltp3  < sellclose  < selltp2:
            
                msg = "TP2 Triggered"
            elif selltp1 < sellclose  < selltp2:
            
                msg = "TP1 Triggered"
            elif sellclose > sellstoploss:
            
                msg = "Stoploss Triggered"
            message = (
                 "<b>"+ stock + "</b>"
                + "  "
                + "<b>SELLCLOSE </b>"
                + "<b>" + str(df.loc[i,"sellclose"])+ "</b>" + "\n "
                + "  "
                + str(msg) + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
                )


            # send_telegram_signal("param", debugmessage,"-1001763597956")
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df.loc[i,"datetime"]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df.loc[i,"notes"]
            data["profitloss"] = profitloss
            data["duration"] = duration
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)


            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
           
            if backtesting:
                print(data)
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
            

            position = 1
            trade = 0
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", message,chat_id)
                if stock == "GOLD":
                    send_telegram_signal("param", message, chat_id)

    return "successfully"



@shared_task()
def send_running_signal(df, i,stock,myportfolio_id, categoryId,notes,istelegram,islive,backtesting):

    _trade = stock + "_trade"
    _position = stock + "_position"
    _stockprice = stock + "_stockprice"
    _stocktime = stock + "_stocktime"

    
    _buystoploss = stock + "_buystoploss"
    _buytp1 = stock + "_buytp1"
    _buytp2 = stock + "_buytp2"
    _buytp3 = stock + "_buytp3"
    _sellstoploss = stock + "_sellstoploss"
    _selltp1 = stock + "_selltp1"
    _selltp2 = stock + "_selltp2"
    _selltp3 = stock + "_selltp3"

    position = localStorage.getItem(_position)
    trade = localStorage.getItem(_trade)
    stockprice = localStorage.getItem(_stockprice)
    stocktime = localStorage.getItem(_stocktime)


    if position is None:
        position = 1
    if trade is None:
        trade = 0
    if stockprice is None:
        stockprice = 0
    if stocktime is None:
        stocktime = 0


    position = int(position)
    trade = int(trade)
   
   
    try:
        buy = df.loc[i,"buy"] 
    except:
        df["buy"] = 0
    try:
        buyclose = df.loc[i,"buyclose"] 
    except:
        df["buyclose"] = 0
    try:
        sell = df.loc[i,"sell"] 
    except:
        df["sell"] = 0
    try:
        sellclose = df.loc[i,"sellclose"] 
    except:
        df["sellclose"] = 0

    #### chat_id = -1001763597956

    if df.loc[i,"buy"] > 0:
        
        
        if position == 1 and trade == 0:
            signal = "BUY"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(pytz.utc)
            debugmessage = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>BUY </b>"
                + "<b>" + str(df.loc[i,"buy"])+ "</b>" + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Upperpoint "
                + str(df.loc[i,"upperpoint"]) + "\n "
                + "Lowerpoint "
                + str(df.loc[i,"lowerpoint"]) + "\n "
                + "Stoploss "
                + str(df.loc[i,"s5underbuy"]) + "\n "
                + "TP1 "
                + str(df.loc[i,"p5superbuy"]) + "\n "
                + "TP2 "
                + str(df.loc[i,"p10superbuy"]) + "\n "
                + "TP3 "   
                + str(df.loc[i,"p20superbuy"]) + "\n "
            )
            localStorage.setItem(_buystoploss,df.loc[i,"s5underbuy"] )
            localStorage.setItem(_buytp1, df.loc[i,"p5superbuy"] )
            localStorage.setItem(_buytp2, df.loc[i,"p7superbuy"] )
            localStorage.setItem(_buytp3, df.loc[i,"p10superbuy"] )
            send_telegram_signal("param", debugmessage,"-1001763597956")
        
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df["datetime"].iloc[i]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df["notes"].iloc[i]
            data["analysis"] = i
           
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)

            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
            position = 2
            trade = 1
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
            localStorage.setItem(_stockprice, close)
            localStorage.setItem(_stocktime, df["datetime"].iloc[i])
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", debugmessage,chat_id)
                if stock == "GOLD":
                    # send_telegram_signal("param", message, "-1001881568384")
                    send_telegram_signal("param", debugmessage, chat_id)

    elif df.loc[i,"buyclose"] > 0:

       
        if position == 2 and trade == 1:
            msg = ""
            buystoploss = localStorage.getItem(_buystoploss )
            buytp1 = localStorage.getItem(_buytp1 )
            buytp2 =  localStorage.getItem(_buytp2 )
            buytp3 = localStorage.getItem(_buytp3 )
            buyclose = str(df.loc[i,"buyclose"])

            if buyclose > buytp3:
                # ic(buyclose,buytp3)
            
                msg = "TP3 Triggered"
            elif buytp2 < buyclose < buytp3:
                # ic(buytp2,buyclose,buytp3)
            
                msg = "TP2 Triggered"
            elif buytp1 < buyclose  < buytp2:
                # ic(buytp1,buyclose,buytp2)
            
                msg = "TP1 Triggered"
            elif buyclose < buystoploss:
                # ic(buyclose,buystoploss)
            
                msg = "Stoploss Triggered"

            
            starttime = localStorage.getItem(_stocktime)
            signal = "BUYCLOSE"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(
                pytz.utc
            )
            stockprice = localStorage.getItem(_stockprice) 
            profitloss = close - float(stockprice)
            starttime = dt.fromisoformat(str(starttime)).astimezone(pytz.utc)
            duration = str(signaldate - starttime)
            profitloss = round(profitloss,2)
            if profitloss > 0:
                profitstring = '<b>' + str(profitloss) + '</b>'
            else:
                profitstring = '<b>' + str(profitloss) + '</b>'

            debugmessage = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>BUYCLOSE </b>"
                + "<b>" + str(df.loc[i,"buyclose"])+ "</b>" + "\n "
                + " "
                + str(msg) + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
            )
            send_telegram_signal("param", debugmessage,"-1001763597956")
         
            message = (
                stock
                + " "
                + str(signal)
                + " "
                + str(close) + "\n "
                + "Time "
                + str(signaldate)  + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
                + "Analysis: "
                + str(df["notes"].iloc[i]) + "\n "
            )
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df.loc[i,"datetime"]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df.loc[i,"notes"]
            data["profitloss"] = profitloss
            data["duration"] = duration
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                ic(serializer.errors)

            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
         
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
         
            position = 1
            trade = 0
            localStorage.setItem(_position, position) 
            localStorage.setItem(_trade, trade) 
           ### chat_id = -1001763597956
            if istelegram:
                    send_telegram_signal("param", debugmessage,chat_id)
                    if stock == "GOLD":
                        send_telegram_signal("param", debugmessage, chat_id)
    elif df.loc[i,"sell"] > 0:
        if position == 1 and trade == 0:
            debugmessage = (
                "<b>"+ stock + "</b>"
                + "  "
                + "<b>SELL </b>"
                + "<b>" + str(df.loc[i,"sell"])+ "</b>" + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Upperpoint "
                + str(df.loc[i,"upperpoint"]) + "\n "
                + "Lowerpoint "
                + str(df.loc[i,"lowerpoint"]) + "\n "
                + "Stoploss "
                + str(df.loc[i,"s3undersell"]) + "\n "
                + "TP1 "
                + str(df.loc[i,"p5supersell"]) + "\n "
                + "TP2 "
                + str(df.loc[i,"p10supersell"]) + "\n "
                + "TP3 "   
                + str(df.loc[i,"p20supersell"]) + "\n "
            )

            localStorage.setItem(_sellstoploss,df.loc[i,"s5undersell"] )
            localStorage.setItem(_selltp1, df.loc[i,"p5supersell"] )
            localStorage.setItem(_selltp2, df.loc[i,"p10supersell"] )
            localStorage.setItem(_selltp3, df.loc[i,"p20supersell"] )
            send_telegram_signal("param", debugmessage,"-1001763597956")

            signal = "SELL"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(pytz.utc)
            message = (
                stock
                + " "
                + str(signal)
                + " "
                + str(close) + "\n "
                + "Time "
                + str(signaldate)  + "\n "
                + "Analysis: "
                + str(df["notes"].iloc[i]) + "\n "
            )
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df["datetime"].iloc[i]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df["notes"].iloc[i]
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)
            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
          
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
            

            position = 3
            trade = 1
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
            localStorage.setItem(_stockprice, close)
            localStorage.setItem(_stocktime, df["datetime"].iloc[i])
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", debugmessage,chat_id)
                if stock == "GOLD":
                    send_telegram_signal("param", debugmessage, chat_id)
    elif df.loc[i,"sellclose"] > 0:
        if position == 3 and trade == 1:
            
           
            signal = "SELLCLOSE"
            close = df["close"].iloc[i]
            signaldate = dt.fromisoformat(str(df["datetime"].iloc[i])).astimezone(
                pytz.utc
            )
            stockprice = localStorage.getItem(_stockprice) 
            profitloss =  float(stockprice) - close 
            starttime = localStorage.getItem(_stocktime)
            starttime = dt.fromisoformat(str(starttime)).astimezone(pytz.utc)
            duration = str(signaldate - starttime)
            profitloss = round(profitloss,2)
            if profitloss > 0:  
                profitstring = '<b style="color:green">' + str(profitloss) + '</b>'
            else:
                profitstring = '<b style="color:red">' + str(profitloss) + '</b>'

            message = (
                stock
                + " "
                + str(signal)
                + " "
                + str(close) + "\n "
                + "Time "
                + str(signaldate)  + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
                + "Analysis: "
                + str(df["notes"].iloc[i]) + "\n "
            )

            

            msg = ""
            sellstoploss = float(localStorage.getItem(_sellstoploss ))
            selltp1 = float(localStorage.getItem(_selltp1 ))
            selltp2 =  float(localStorage.getItem(_selltp2 ))
            selltp3 =  float(localStorage.getItem(_selltp3 ))
            sellclose = float(df.loc[i,"sellclose"])
            ic(sellclose,selltp1,selltp2,selltp3)

            if sellclose < float(selltp3):
       
                msg = "TP3 Triggered"
            elif selltp3  < sellclose  < selltp2:
       
                msg = "TP2 Triggered"
            elif selltp1 < sellclose  < selltp2:
            
                msg = "TP1 Triggered"
            elif sellclose > sellstoploss:
          
                msg = "Stoploss Triggered"
            debugmessage = (
                 "<b>"+ stock + "</b>"
                + "  "
                + "<b>SELLCLOSE </b>"
                + "<b>" + str(df.loc[i,"sellclose"])+ "</b>" + "\n "
                + "  "
                + str(msg) + "\n "
                + "Date "
                + str(df.loc[i,"datetime"]) + "\n "
                + "Profitloss "
                + str(profitstring) + "\n "
                + "Duration "
                + str(duration) + "\n "
                )


            send_telegram_signal("param", debugmessage,"-1001763597956")
            #print(message)
            chat_id = Category.objects.get(id=categoryId).chat_id
            data = {}
            data["org_id"] = 1
            data["signaldate"] = df["datetime"].iloc[i]
            data["stock"] = stock
            data["signals"] = signal
            data["price"] = close
            data["chat_id"] = chat_id
            data["notes"] = df["notes"].iloc[i]
            data["profitloss"] = profitloss
            data["duration"] = duration
            data["analysis"] = i
            serializer = send_signals_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)


            #1 - Insert the demo Trade code here. 
            if islive:
                trade_signal("self",stock,myportfolio_id,data, "demo")
                trade_signal("self",stock,myportfolio_id,data, "live")
                trade_signal("self",stock,myportfolio_id,data, "signals")
            
            if backtesting:
                trade_signal("self",stock,myportfolio_id,data, "backtesting")
          

            position = 1
            trade = 0
            localStorage.setItem(_position, position)
            localStorage.setItem(_trade, trade)
           ### chat_id = -1001763597956
            if istelegram:
                send_telegram_signal("param", debugmessage,chat_id)
                if stock == "GOLD":
                    send_telegram_signal("param", debugmessage, chat_id)

    return "successfully"


@shared_task()
def repair_stockdata():
    message = "stockdata"
    updatestock = {}
    updatestock['slowanchorma'] = 200
    updatestock['veryslowanchorma'] = 300
    stockInstance = stockdata.objects.all().update(slowanchorma=200,veryslowanchorma=300)
    return message



@shared_task()
def myportfolio_profitloss(myportfolio_id):
    starttime = dt.utcnow() + timedelta(hours=8)
    item = roboportfolio.objects.filter(myportfolio_id=myportfolio_id).order_by("-id")
    roboserializer = RoboportfolioSerializer(item, many=True)
  
    
    for robodata in roboserializer.data:
        print(robodata['stock'])
        calculateprofit(stock=robodata['stock'],myportfolio_id=myportfolio_id)
        portfolioprofit(myportfolio_id)


    stoptime = dt.utcnow() + timedelta(hours=8)
    duration = stoptime - starttime

    print("starttime", starttime)
    print("stoptime", stoptime)
    print("duration", duration)

from adx.robotscanner import RobotScanner
robotscanner = RobotScanner()



@shared_task()
def calculateprofit(stock,myportfolio_id):
  
    position = 1
    profit_loss = 0
    total_profit = 0
    winrate = 0

    df = pd.DataFrame(list(demo_trades.objects.filter(stock=stock,myportfolio_id=myportfolio_id).values()))

   
    sf = pd.DataFrame(
            columns=[
                "stock",
                "start_datetime",
                "stop_datetime",
                "duration",
                "direction",
                "buy",
                "buyclose",
                "sell",
                "sellclose",
                "profit_loss",
                "percentage_profit",
                "total_profit",
                "customer_id",
                "myportfolio_id",

            ]
        )
    j = 1
    for i, row in df.iterrows():
        if i >= 1:
            prev = i-1 
            if df.loc[i, "signals"] =='BUYCLOSE':
              
                buyclose = df.loc[i, "price"]
                buyclose = round(buyclose, 2)
                stop_datetime = df.loc[i, "signaldate"]
                buy = df.loc[prev, "price"]
                buy = round(buy, 2)
                start_datetime = df.loc[prev, "signaldate"]
                profit_loss = float(buyclose) - float(buy)
                if profit_loss > 0:
                    winrate = winrate + 1
                total_profit = total_profit + profit_loss
                total_profit = round(total_profit, 2)

                start_datetime = df.loc[prev, "signaldate"]
                
                duration = str(stop_datetime - start_datetime)
                percentage_profit = round(profit_loss / buy * 100, 2)
                customer_id = df.loc[i, "customer_id"]
                myportfolio_id = df.loc[i, "myportfolio_id"]
                
                sf.loc[j] = [
                            stock,
                            start_datetime,
                            stop_datetime,
                            duration,
                            'BUY',
                            buy,
                            buyclose,
                            0,
                            0,
                            profit_loss,
                            percentage_profit,
                            total_profit,
                            customer_id,
                            myportfolio_id

                        ]
                print(sf.loc[j])
                j = j + 1
        

            elif df.loc[i, "signals"] =='SELLCLOSE':

                sellclose = df.loc[i, "price"]
                sellclose = round(sellclose, 2)
            
                stop_datetime = df.loc[i, "signaldate"]
            
                sell = df.loc[prev, "price"]
                sell = round(sell, 2)
                profit_loss = float(sell) - float(sellclose)
                percentage_profit = round(profit_loss / sell * 100, 2)
                if profit_loss > 0:
                    winrate = winrate + 1
                total_profit = total_profit + profit_loss
                total_profit = round(total_profit, 2)
                start_datetime = df.loc[prev, "signaldate"]
                duration = str(stop_datetime - start_datetime)
                customer_id = df.loc[i, "customer_id"]
                myportfolio_id = df.loc[i, "myportfolio_id"]
             

                sf.loc[j] = [
                    stock,
                    start_datetime,
                    stop_datetime,
                    duration,
                    'SELL',
                    sell,
                    sellclose,
                    0,
                    0,
                    profit_loss,
                    percentage_profit,
                    total_profit,
                    customer_id,
                    myportfolio_id
                ]
                print(sf.loc[j])
                j = j + 1
                

    sf.replace(0, np.nan)
    sf["org_id"] = 1
    sf["json"] = sf.to_json(orient="records", date_format="iso", date_unit="s", lines=True).splitlines()
    sf = sf.reset_index()

    
    tf = pd.DataFrame(sf)
    portfolio_profit_loss.objects.filter(stock=stock).delete()
    

    if len(sf.index) > 1:
        for i in range(len(sf.index)):
            # print(i)
            # print(sf.loc[i, "json"])
            
            serializer = portfolio_profit_loss_serializer(data=json.loads(sf.loc[i, "json"]))
            if serializer.is_valid():
                serializer.save()
            else:
                print(serializer.errors)
       
        
    return tf,winrate


@shared_task()
def portfolioprofit(myportfolio_id):

    UserPortfolioInstance = userportfolio.objects.get(id=myportfolio_id)
    portfolio_capital = UserPortfolioInstance.portfolio_capital
    item = roboportfolio.objects.filter(myportfolio_id=myportfolio_id).order_by("-id")
    serializer = RoboportfolioSerializer(item, many=True)
    portfolio_profitloss = 0
    
    for data in serializer.data:     
        stock_profitloss = 0
        winrate = 0
        totaltrades = 0
        pnLInstance = portfolio_profit_loss.objects.filter(stock= data['stock'],myportfolio_id=myportfolio_id).order_by("id")
        pnLserializer = portfolio_profit_loss_serializer(pnLInstance, many=True)
        
        for pnldata in pnLserializer.data:
            stock_profitloss = stock_profitloss + pnldata['profit_loss']
            stock_profitloss = round(stock_profitloss,2)
            if pnldata['profit_loss'] > 0:
                winrate = winrate + 1
            totaltrades = totaltrades + 1
            
        if winrate > 0:
            percentagewin = winrate / totaltrades * 100
        else:
            percentagewin = 0
            
        print("capital", data['allocatedvalue']) 
        print("profitloss", stock_profitloss)
        print("percentagewin", percentagewin)

        
        percentage_profit = round(stock_profitloss / data['allocatedvalue'] * 100, 2)
        print("percentage_profit", percentage_profit)
        portfolio_profitloss = portfolio_profitloss + stock_profitloss
        
        updatestock = {}
        updatestock['profitloss'] = stock_profitloss
        updatestock['percentagepnl'] = percentage_profit
        updatestock['winrate'] = winrate
        updatestock['totaltrades'] = totaltrades
        updatestock['percentagewin'] = round(percentagewin,2)
     
            
        RoboportfolioInstance = roboportfolio.objects.get(myportfolio_id=myportfolio_id,stock=data['stock'])
        updateserializer = RoboportfolioSerializer(RoboportfolioInstance, data=updatestock,partial=True)
        if updateserializer.is_valid():
            updateserializer.save()
            print("updateserializer updated")
        else:
            print(updateserializer.errors)
    try:
        portfolio_startdate = portfolio_profit_loss.objects.filter(myportfolio_id=myportfolio_id).first().start_datetime
    except:
        portfolio_startdate = dt.now()
    portfolio_enddate = dt.now()
    starttime = portfolio_startdate.replace(tzinfo=pytz.UTC)
    stoptime = portfolio_enddate.replace(tzinfo=pytz.UTC)
    duration = stoptime - starttime

    new_capital = portfolio_capital + portfolio_profitloss
    print("new_capital", new_capital)
    print("duration", duration)
   
    profitlossPercentage = round(portfolio_profitloss / portfolio_capital * 100, 2)
    userportfoliodata = {}
    userportfoliodata['newCapital'] =  round(new_capital,2)
    userportfoliodata['portfolioProfitloss'] =  round(portfolio_profitloss,2)
    userportfoliodata['profitlossPercentage'] =  round(profitlossPercentage,2)
    userportfoliodata['duration'] =  str(duration)
    userportfoliodata['portfolio_startdate'] =  portfolio_startdate
    userportfoliodata['winrate'] =  winrate
    userportfoliodata['totaltrades'] =  totaltrades

    ic(userportfoliodata)
    serializer = userportfolioSerializer(UserPortfolioInstance,data=userportfoliodata,partial=True)
    if serializer.is_valid():
        serializer.save()
        print("userportfolio updated")
    else:
        print(serializer.errors)
    
    ResponseJson = {
        "status": "success",
        "porfolio-profitloss" : round(portfolio_profitloss,2),
        "duration" : duration,
        "new_capital" : new_capital
    }

    return ResponseJson

 

@shared_task()

def strategy80_test(stock, source, categoryId,minloss,minprofit,pos,neg,meantrade=1.2,timing=3, atr_period=18, multiplier=3,tradetype=0,running=1):

    ic(stock,minloss,minprofit,pos,neg)
    if timing == 1:
        tf = robotscanner.get_1day_data(stock, source)
    if timing == 3:
        tf = robotscanner.get_3min_data(stock, source)
    elif timing == 5:
        tf = robotscanner.get_5min_data(stock, source)
    elif timing == 15:
        tf = robotscanner.get_15min_data(stock, source)

    for i in range(5000,5001,1):
        af = tf[0:i]
        ti.sleep(1)
        af.reset_index(inplace=True)

        af = robotscanner.get_slowmovingaverage(af)
        af = robotscanner.pullback_avg(af)
        af = robotscanner.new_indicators(af)
        af = robotscanner.analysis1(af,meantrade)
        af = robotscanner.minmaxc2(af)

        af['HMA50'] =  af['c2']
        af["org_id"] = 1
        af["stock"] = stock
        af["source"] = source
        af["myportfolio_id"] = 1
        af["rmin"] = af['smin']
        af['rmax'] = af['smax']
        af.reset_index(inplace=True)
        df = strategy2_running(stock, af, 3, 1,minloss,minprofit,pos,neg,tradetype,backtest=0)
        
        i = len(df.index) -1 
        notes = "Testing"
        send_signal(df,i, stock, categoryId, notes,0)
        ilen = len(df.index)
        
        df = df.replace([0],np.nan)
        

        graphname = stock + str(ilen)
        graphviewpositive(graphname,df)
        # save2googlesheet(df,"pullback-stats",0)

                        
    
    return df



  