
import simplejson

from sqlobject import *

# Replace this with the URI for your actual database
connection = connectionForURI('sqlite:qtbot.db')
sqlhub.processConnection = connection

class Profitloss(SQLObject):
    stock = StringCol(length=200, default=None)
    start_datetime = StringCol(length=200, default=None)
    stop_datetime = StringCol(length=200, default=None)
    duration = StringCol(length=200, default=None)
    direction = StringCol(length=200, default=None)
    buy = DecimalCol(default="",size=4,precision=3)
    buyclose = DecimalCol(default="",size=4,precision=3)
    sell = DecimalCol(default="",size=4,precision=3)
    sellclose = DecimalCol(default="",size=4,precision=3)
    profit_loss = DecimalCol(default="",size=4,precision=3)
    percentage_profit = DecimalCol(default="",size=4,precision=3)
    total_profit = DecimalCol(default="",size=4,precision=3)
  

# Create fake data for demo - this is not needed for the real thing
def MakeFakeDB():
    Profitloss.dropTable()
    Profitloss.createTable()
    s1 = Profitloss(
            stock = "HDFC",
            start_datetime = "HDFC",
            stop_datetime = "HDFC",
            duration = "HDFC",
            direction = "HDFC",
            buy = 22.34,
            buyclose = 22.34,
            sell = 22.34,
            sellclose = 22.34,
            profit_loss = 22.34,
            percentage_profit = 22.34,
            total_profit = 22.34,
    )
    s2 = Profitloss(
            stock = "HDFC",
            start_datetime = "HDFC",
            stop_datetime = "HDFC",
            duration = "HDFC",
            direction = "HDFC",
            buy = 22.34,
            buyclose = 22.34,
            sell = 22.34,
            sellclose = 22.34,
            profit_loss = 22.34,
            percentage_profit = 22.34,
            total_profit = 22.34,
    )

def add_data(data):
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

def select_data():
    # This is an iterable, not a list
    print("We are in select table")
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

    response = simplejson.dumps(profitloss_as_dict)
    print(response)
    return response

if __name__ == "__main__":
    MakeFakeDB()
    # add_data()
    select_data()