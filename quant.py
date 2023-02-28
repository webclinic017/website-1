import os
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots
import requests
import math
from tvDatafeed import TvDatafeed, Interval
# from telegram_notifier  import TelegramNotifier
from telegram_notifier import TelegramNotifier
from pathlib import Path
from scipy.signal import argrelextrema
import pygsheets
import pathlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import socket
import talib as ta
import simplejson
import json

from icecream import ic

import sqlite3 as sql
from db.profitloss import Profitloss


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
tv = TvDatafeed()


pd.set_option("mode.chained_assignment", None)


class Quant:
    def getdata(stock, sourceexch,interval,length):
        df = pd.DataFrame()

        df = tv.get_hist(
            symbol=stock,
            exchange=sourceexch,
            interval= Interval(interval) ,
            n_bars=int(length),
        )
        df.reset_index(inplace=True)
        np.round(df, decimals=4)
        df.reset_index(inplace=True)
        # print(dd.info())
        return df


    def crossover(df,param1,param2):
        sell = ((df[param1] < df[param2]) & (df[param1].shift(1) > df[param2].shift(1)))
        buy = ((df[param1] > df[param2]) & (df[param1].shift(1) < df[param2].shift(1)))
        sell = np.where(sell > 0, df["close"], "NaN")
        buy = np.where(buy > 0, df["close"], "NaN")
       
        return buy,sell

    def save2csv(stock,df):
        # print(df)
        current_dir = str(Path(__file__).parent)
        filename = stock + ".csv"
        path_to_file = current_dir + "/csv/" + filename
        checkfile = Path(path_to_file)
        if checkfile.is_file():
            os.remove(path_to_file)
        else:
            df.to_csv(path_to_file, mode="w", index=False, header=True)
       
        return "CSV Created"

    def getcsv(stock):
        current_dir = str(Path(__file__).parent)
        filename = stock + ".csv"
        path_to_file = current_dir + "/csv/" + filename
        df = pd.read_csv(path_to_file)
        return df


    def save2googlesheet(df, sheetname, sheetnumber):
        sheetnumber = int(sheetnumber)
        numberofrows = len(df.index)
        if numberofrows > 1500:
            df = df.iloc[-1500:]

        # df = df.iloc[::-1]
        current_dir = str(Path(__file__).parent)
        filename = "gsheets.json"
        filename = current_dir + "/" + filename
        gc = pygsheets.authorize(service_file=filename)
        sh = gc.open(sheetname)
        wks1 = sh[sheetnumber]
        wks1.clear()
        wks1.set_dataframe(df, (0, 0))
       
    def graph(stock, df):
        # numberofrows = len(df.index)
        # if numberofrows > 600:
        #     df = df[-200:]
        fig = go.Figure()

        # df['datetime'] = df['datetime'] + timedelta(hours=8)
        # declare figure
        # Create subplots and mention plot grid size

        fig = make_subplots(
            rows=1,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("OHLC", "Volume"),
        )

        fig.add_trace(go.Scatter(x=df['index'], y=df['close'], line_shape='spline', line_smoothing=1.3,
                                line=dict(color='blue', width=.7), name='close'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['index'], y=df['ma'], line_shape='spline', line_smoothing=1.3,
                                line=dict(color='orange', width=.7), name='ma'), row=1, col=1)
    
        fig.add_trace(go.Scatter(x=df['index'], y=df['ema'], line_shape='spline', line_smoothing=1.3,
                                    line=dict(color='purple', width=.7), name='ema'), row=1, col=1)
        
        try:
            fig.add_trace(
                go.Scatter(
                    x=df["index"],
                    y=df["buy"],
                    mode="markers",
                    name="buy",
                    line=dict(width=1, color="green"),
                ),row=1, col=1
            )
        except:
            print("no attributes as buy")

        try:
            fig.add_trace(
                go.Scatter(
                    x=df["index"],
                    y=df["buyclose"],
                    mode="markers",
                    name="buyclose",
                    line=dict(width=1, color="darkblue"),
                    
                ),row=1, col=1
            )
        except:
            print("no attributes as buy")

        try:
            fig.add_trace(
                go.Scatter(
                    x=df["index"],
                    y=df["sell"],
                    mode="markers",
                    name="sell",
                    line=dict(width=1, color="red"),
                ),row=1, col=1
            )
        except:
            print("no attributes as sell")


        try:
            fig.add_trace(
                go.Scatter(
                    x=df["index"],
                    y=df["sellclose"],
                    mode="markers",
                    name="sellclose",
                    line=dict(width=1, color="orange"),
                ),row=1, col=1
            )
        except:
            print("no attributes as sellclose")


        fig.update_layout(title=stock, yaxis_title="OHLC", height=900, width=1500)
        fig.update(layout_xaxis_rangeslider_visible=False)
        fig.show()


    

    def backteststategy(stock,datadf):
        df = datadf[(datadf.signals == "Buy" ) | (datadf.signals == "Sell") | (datadf.signals == "Buyclose" ) | (datadf.signals == "Sellclose") ]
        print(df)
        df.reset_index(inplace=True)

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
                        "total_profit"
                    ]
                )


        winrate = 0
        total_profit = 0
        j = 1
        for i, row in df.iterrows():
            if i >= 1:
                prev = i-1 
                if df.loc[i, "signals"] =='Buyclose':
                
                    buyclose = df.loc[i, "close"]
                    buyclose = round(buyclose, 4)
                    stop_datetime = df.loc[i, "datetime"]
                    buy = df.loc[prev, "close"]
                    buy = round(buy, 4)
                    start_datetime = df.loc[prev, "datetime"]
                    profit_loss = float(buyclose) - float(buy)
                    if profit_loss > 0:
                        winrate = winrate + 1
                    total_profit = total_profit + profit_loss
                    total_profit = round(total_profit, 2)

                    start_datetime = df.loc[prev, "datetime"]
                    duration = str(stop_datetime - start_datetime)
                    percentage_profit = round(profit_loss / buy * 100, 2)
                
                    
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
                            ]
                    j = j + 1
            

                elif df.loc[i, "signals"] =='Sellclose':

                    sellclose = df.loc[i, "close"]
                    sellclose = round(sellclose, 4)
                
                    stop_datetime = df.loc[i, "datetime"]
                    sell = df.loc[prev, "close"]
                    sell = round(sell, 4)
                    profit_loss = float(sell) - float(sellclose)
                    percentage_profit = round(profit_loss / sell * 100, 2)
                    if profit_loss > 0:
                        winrate = winrate + 1
                    total_profit = total_profit + profit_loss
                    total_profit = round(total_profit, 2)
                    start_datetime = df.loc[prev, "datetime"]
                    duration = str(stop_datetime - start_datetime)
    
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
                        total_profit
                    ]
                    j = j + 1
        
        total_trades = sf.shape[0]
        sf["json"] = sf.to_json(orient="records", date_format="iso", date_unit="s", lines=True).splitlines()
        sf = sf.reset_index()
        return sf, total_trades,  winrate,total_profit





    def getgraphdata(df):
        df["json"] = df.to_json(orient="records", date_format="iso", date_unit="s", lines=True).splitlines()
        df = df.reset_index()

        graphapi = []

        for i, row in df.iterrows():
            
            jsondata = df.loc[i, "json"]
            json_object = json.loads(jsondata)
            graphapi.append(json_object)

        
        
        # print(type(Responsejson))
        return graphapi


    def buyandholdcalculation(df):
        print("step4")
        startprice = df["close"].iloc[0]
        endprice = df["close"].iloc[-1]
        startdate = df["datetime"].iloc[0]
        enddate = df["datetime"].iloc[-1]
        profitloss = endprice - startprice 
        duration = enddate - startdate 
        # print(profitloss)
        # print(duration)


    def checkbuysell(df):
        position = 1
        for i, row in df.iterrows():
            prev1, prev2, prev3 = i - 1, i - 2, i - 3
            
            if position == 1:
                if float(df.loc[i, "buy"]) > 0 :     
                        buy =  df.loc[i, "close"]
                        notes = df.loc[i, "signals"] = "Buy"
                        position  = 2

                if float(df.loc[i, "sell"]) > 0 :     
                        sell =  df.loc[i, "close"]
                        notes = df.loc[i, "signals"] = "Sell"
                        position  = 3

            elif position == 2:
                if float(df.loc[i, "buyclose"]) > 0 :     
                        buyclose =  df.loc[i, "close"]
                        notes = df.loc[i, "signals"] = "Buyclose"
                        profitloss = df.loc[i,"profitloss"] = buyclose - buy
                        position  = 1

            elif position == 3:
                if float(df.loc[i, "sellclose"]) > 0 :     
                        sellclose =  df.loc[i, "close"]
                        notes = df.loc[i, "signals"] = "Sellclose"
                        profitloss = df.loc[i,"profitloss"] = sell - sellclose
                        position  = 1
                    
        return df


    def triggeralerts(df):
        print("trigger signal")
        signals = df["signals"].iloc[-1]
        if signals == "Buy":
        
            payload = {
                "signal": [
                    "BUY"
                ]
            }
            res = requests.post('external/api/url', data=payload)
            print('this is the true http resonse: ',res.status_code)
            data = res.json()
            
            return data

    def insertprofitloss(df):
        Profitloss.dropTable()
        Profitloss.createTable()

        for i, row in df.iterrows():
            loaddata = df.loc[i,"json"]
            
            data = json.loads(loaddata)
            stock = data["stock"]
            start_datetime = data['start_datetime']
            stop_datetime  = data['stop_datetime']
            duration  = data['duration']
            direction  = data['direction']
            buy  = data['buy']
            buyclose  = data['buyclose']
            sell  = data['sell']
            sellclose  = data['sellclose']
            profit_loss  = data['profit_loss']
            percentage_profit  = data['percentage_profit']
            total_profit  = data['total_profit']


            Profitloss(
                    stock = stock,
                    start_datetime =start_datetime,
                    stop_datetime = stop_datetime,
                    duration = duration,
                    direction = direction,
                    buy = buy,
                    buyclose= buyclose,
                    sell = sell,
                    sellclose = sellclose,
                    profit_loss = profit_loss,
                    percentage_profit = percentage_profit,
                    total_profit = total_profit,
            )
            
        return df


    def showprofitloss():
        results = Profitloss.select().orderBy(Profitloss.q.id)
        print(results.count())
        profitloss_as_dict = []

        for profitloss in results:
            row = {
                'stock' : profitloss.stock ,
                'start_datetime' : profitloss.start_datetime ,
                'stop_datetime' : profitloss.stop_datetime ,
                'duration' : profitloss.duration ,
                'direction' : profitloss.direction ,
                'buy' : profitloss.buy ,
                'buyclose' : profitloss.buyclose ,
                'sell' : profitloss.sell ,
                'sellclose' : profitloss.sellclose ,
                'profit_loss' : profitloss.profit_loss ,
                'percentage_profit' : profitloss.percentage_profit ,
                'total_profit' : profitloss.total_profit ,
                    
                }

            profitloss_as_dict.append(row)

        response = simplejson.dumps(profitloss_as_dict,separators=(',',':'), sort_keys=True)
        return response

    def strategy(df):
        print("step3")
        df['ma'] = ta.SMA(df['close'],timeperiod=21)
        df['ema'] = ta.EMA(df['close'], timeperiod = 5)
        buy,sell = Quant.crossover(df,"close","ema")
        df["sellclose"] = buy
        df["buyclose"] = sell
        df["sell"] = df["buyclose"].shift(1)
        df["buy"] = df["sellclose"].shift(1)

        return df
