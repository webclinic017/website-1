import sqlite3 as sql
import json
import simplejson

from sqlobject import *
import os

connection = connectionForURI('sqlite:./qtbot.db')
sqlhub.processConnection = connection

class ProfitLoss:
    def create_table(sql):
        print("create profitloss table")
        con = sql.connect('qtbot.db')
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS profitloss")
        #Create users table  in db_web database
        sql ='''CREATE TABLE "profitloss" (
            "id"	INTEGER PRIMARY KEY AUTOINCREMENT,
            "stock"	TEXT,
            "start_datetime"	TEXT,
            "stop_datetime"	TEXT,
            "duration"	TEXT,
            "direction"	TEXT,
            "buy"	decimal(10,5),
            "buyclose"	decimal(10,5),
            "sell"	decimal(10,5),
            "sellclose"	decimal(10,5),
            "profit_loss"	decimal(10,5),
            "percentage_profit"	decimal(10,5),
            "total_profit" 	decimal(10,5)
        )'''
        cur.execute(sql)
        con.commit()
        con.close()


    def select_data(sql):
        con=sql.connect("qtbot.db")
        con.row_factory=sql.Row
        cur=con.cursor()
        cur.execute("select * from profitloss")
        data=cur.fetchall()
        res = json.dumps( [dict(ix) for ix in data] ) 

        print("response in profitloss -- ")
        print(res)
        return res


    def add_data(data,sql):
        data = json.loads(data)
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
        # print(stock,start_datetime,stop_datetime,duration,direction,buy,buyclose,\
        #     sell,sellclose,profit_loss,percentage_profit,total_profit)

        con=sql.connect("qtbot.db")
        cur=con.cursor()
        statement = "insert into profitloss(stock,start_datetime,stop_datetime,duration,direction,buy,buyclose,\
            sell,sellclose,profit_loss,percentage_profit,total_profit) values (?,?,?,?,?,?,?,?,?,?,?,?)"
      
        cur.execute(statement,(stock,start_datetime,stop_datetime,duration, \
            direction ,buy ,buyclose ,sell ,sellclose ,profit_loss  ,percentage_profit  ,total_profit ))
        con.commit()


    def select_data(sql):
        

        con=sql.connect("qtbot.db")
        con.row_factory=sql.Row
        cur=con.cursor()
        cur.execute("select * from profitloss")
        data=cur.fetchall()
        return data
    


    def select_single_data(uid,sql):
        con=sql.connect("qtbot.db")
        con.row_factory=sql.Row
        cur=con.cursor()
        cur.execute("select * from users")
        data=cur.fetchall()
        return data

            
    def edit_data(uid,data,sql):
        uname=data['uname']
        contact=data['uname']
        con=sql.connect("qtbot.db")
        cur=con.cursor()
        cur.execute("update users set UNAME=?,CONTACT=? where UID=?",(uname,contact,uid))
        con.commit()
        
    def delete_data(uid):
        con=sql.connect("qtbot.db")
        cur=con.cursor()
        cur.execute("delete from users where UID=?",(uid,))
        con.commit()
       


