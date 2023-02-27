
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import talib as ta

from  quant import Quant
from  db.user import User
from  db.profitloss import Profitloss

import sqlite3 as sql

class Api():
    def run():
        print("command promt")
        stock = "NAS100USD"
        sourceexch = "OANDA"
        interval = "15"
        length = 200
        googlesheetname = "MA Backtesting"
        googlesheetnumber = 0


    def backtest(data):
        print(data)
        df = Quant.getdata(data['stock'], data['sourceexch'],data['interval'],data['length'])
        df = Quant.strategy(df)
        message = Quant.save2csv(data['stock'],df)
        df = Quant.checkbuysell(df)
        Quant.buyandholdcalculation(df)
        Quant.graph(data['stock'],df)
        Quant.save2googlesheet(df, data['googlesheetname'], data['googlesheetnumber'])
        Quant.triggeralerts(df)
        sf,total_trades, winrate,total_profit = Quant.backteststategy(data['stock'],df)
        Quant.insertprofitloss(sf)

    def showprofitloss():
        data = Quant.showprofitloss()
        return data 

    def getgraphdata(stock):
        df = Quant.getcsv(stock)
        data = Quant.getgraphdata(df)
        
        return data 

   

