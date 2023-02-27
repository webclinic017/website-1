# Module Imports
from flask import Flask, request, session, redirect, render_template, url_for
import schedule
import threading
import time
from bson.objectid import ObjectId
import psutil



# File Imports
from config import def_username, def_password, app_sec, port

from api import Api

# App Setup
app = Flask(__name__, static_folder="static")

app.secret_key = app_sec
# user & pass
def_username = def_username
def_password = def_password



@app.route('/api/botsettings', methods=['POST'])
def create_task():
    data = request.json
    
    Api.backtest(data)
    return "Success"

# Login Route
@app.route("/", methods = ["GET", "POST"])
def root_route():

    data = {}
    stock = {}
    return render_template("./index.html",data=data,stock=stock, flash_msg=[False, ""])


# Login Route
@app.route("/api/getprofitloss", methods = ["GET","POST"])
def profitloss_route():
    data =  Api.showprofitloss()
    ResponseJson = {"status": "success", "data": data}
    return ResponseJson


# Login Route
@app.route("/api/graphdata", methods = ["GET","POST"])
def graphdata_route():
    stock = "HDFCBANK"
    data =  Api.getgraphdata(stock)
    ResponseJson = {"status": "success", "data": data}
    return ResponseJson

    
if __name__ == "__main__":
    app.run(host='0.0.0.0',port=port,debug=True)

    

    
    




