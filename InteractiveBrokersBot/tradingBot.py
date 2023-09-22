#Imports
import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import *
import ta  
import numpy as np
import pandas as pd
import pytz 
import math
from datetime import datetime, timedelta
import threading
import time

#Variables
orderId = 1  
#class for IB connection
class IBApi(EWrapper,EClient):
    def __init__(self):
        EClient.__init__(self,self)
    #historical datat from before entering session
    def historicalData(self, reqId, bar): 
        try:
            bot.on_bar_update(reqId, bar,False)
        except Exception as e:
            print(e)
    #realtime bar datat after the historical data finishes
    def historicalDataUpdate(self,reqId,bar):
        try:
            bot.on_bar_update(reqId, bar,False)
        except Exception as e:
            print(e)

    def historicalDataEnd(self,reqId,start,end):
        print(reqId)

    #Get next order ID we can use
    def nextvalidId(self, nextorderId):
        global orderId
        orderId= nextorderId        
    #Listen for the live data
    def realtimeBar(self, reqId, time, open_, high, low, close, volume, wap, count):
        super().realtimeBar(self, reqId, time, open_, high, low, close, volume, wap, count)
        try:
            bot.on_bar_update(reqId, time, open_, high, low, close, volume, wap, count)
        except Exception as e:
            print(e)
#Handles bar data from IB
class Bar():
    open = 0
    low =0
    high = 0 
    close = 0
    volume = 0
    data = '' 
    def __init__(self):
        self.open = 0
        self.open = 0
        self.high = 0 
        self.close = 0
        self.volume = 0
        self.data = ''

#Class for the bot
class Bot():
    ib = None
    barsize = 5
    currentBar  = Bar()
    bars =  []
    reqId = 1
    global orderId
    smaPeriod = 50
    symb = " "
    initbartime = datetime.now().astimezone(pytz.timezone("America/New_York"))
    def __init__(self):
        #Connect to Interactive Broker on init
        self.ib = IBApi()
        self.ib.connect("127.0.0.1", 7497, 1)
        ib_thread = threading.Thread(target = self.run_loop , daemon = True)
        ib_thread.start()
        time.sleep(1)
        currentBar = Bar()
        #get symbol info
        self.symb = input("Enter the symbol you want to trade: ")

        #Get bar sixe
        self.barsize = input("Enter the timefram you want to trade in minutes: ")
        mintext = "min" 
        if(int(self.barsize) > 1):
            mintext = " mins"
        
        queryTime = (datetime.now().astimezone(pytz.timezone("America/New_York")) - timedelta(days=1)).replace(hour=16,minute=0,second=0,microsecond=0).strftime("%Y%m%d %H:%M%S")
        contract = Contract()
        contract.symb = self.symb.upper()
        contract.secType = "IND"
        contract.currency = "USD"
        contract.exchange = "SMART"
        self.ib.reqId(-1)
        
        '''contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD" 
        '''
        #request live market data
        #self.ib.reqRealTimeBars(0, contract, 5, "TRADES", 1, [])
        self.ib.reqHistoricalData(self.reqId, contract, "", "2 D", str(self.barsize)+mintext, "TRADES", 1, 1, True, [])

    #listen to socekt in a seperate thread
    def run_loop(self):
        self.ib.run()
    
    #Bracket order
    def bracketOrder(self, parentOrderId, action, quantity, profitTargetOrder, stoploss):
        #entry
        contract = Contract()
        contract.symb = self.symb.upper()
        contract.secType = "IND"
        contract.currency = "USD"
        contract.exchange = "SMART"
        
        #Create Parent order / initial entry
        parent = Order()
        parent.orderId = parentOrderId
        parent.orderType = "MKT"
        parent.action = action
        parent.totalQuantity = quantity
        parent.transmit = False

        #Profit Targett
        profitTargetOrder = Order()
        profitTargetOrder.orderId = parent.orderId+1
        profitTargetOrder.orderType = "LMT"
        profitTargetOrder.action = "SELL"
        profitTargetOrder.totalQuantity = quantity
        profitTargetOrder.lmtPrice = round(profitTargetOrder, 2)
        profitTargetOrder.transmit = False

        #Stop Loss
        stopLossOrder = Order()
        stopLossOrder.orderId = parent.orderId+2
        stopLossOrder.orderType = "STP"
        stopLossOrder.action = "SELL"
        stopLossOrder.totalQuantity = quantity
        stopLossOrder.auzPrice = round(stopLossOrder, 2)
        stopLossOrder.transmit = True

        bracketOrders = [parent, profitTargetOrder, stopLossOrder]
        return bracketOrders
    
    #pass live data / TRADING STRATEGY
    def on_bar_update(self,reqId, bar,realtime):
        if(realtime == False):
            self.bars.append(bar)
        else:
            bartime = datetime. strptime(bar.date, "%Y%m%d %H:%M%S").astimezone(pytz.timezone("America/New_York"))
            minutes_diff =  (bartime-self.initbartime).total_seconds() / 60.0
            self.currentBar.date = bartime
            #on bar close (ensures that the previous bar is cloed in order to perform logic)
            if(minutes_diff > 0 and math.floor(minutes_diff) % self.barsize == 0):  
                #Entry is we have a higher high, and a higher low and we cross the 50 SMA
                #SMA
                closes = []
                for bar in self.bars:
                    closes.append(bar.close)
                self.close_array = pd.Series(np.asarray(closes))
                self.sma = ta.trenc.sma(self.close_array, self.smaPeriod, True)
                print("SMA: " + str(self.sma[len(self.sma) - 1]))
                #Calc higher highs and lows
                lastLow = self.bars[len(self.bars)-1].low
                lastHigh = self.bars[len(self.bars)-1].high
                lastClose = self.bars[len(self.bars)-1].close
                lastBar = self.bars[len(self.bars)-1]

                #Check the requirements
                if(bar.close > lastHigh
                    and self.currentBar.low > lastLow
                    and bar.close > str(self.sma[len(self.sma) - 1])
                    and lastClose < str(self.sma[len(self.sma) - 2])):

                    #Set profit target and stoploss  
                    profitTarget = bar.close*1.02
                    stoploss = bar.close*0.99  
                    bracket = self.bracketOrder(orderId, "BUY",quantity, profitTarget, stoploss)
                    contract = Contract()
                    contract.symb = self.symb.upper()
                    contract.secType = "IND"
                    contract.currency = "USD"

                    #place bracket order
                    for o in bracket: 
                        o.ocaGroup = "OCA_" + str(orderId)
                        o.ocaType = 2
                        self.ib.placeOrder(o.orderID,o.contract, o)
                        orderId +=3
                #close append
                self.currentBar.close = bar.close  
                if(self.currentBar.date != lastBar.date):
                    print("New BAr")
                    self.bars.append(self.currentBar)
                self.currentBar.open = bar.open

        #build the realtime bar
        if(self.currentBar.open == 0):
            self.currentBar.open = bar.open
        if(self.currentBar.high == 0 or bar.high > self.currentBar.high):
            self.currentBar.high = bar.high
        if(self.currentBar.low == 0 or bar.low < self.currentBar.low):
            self.currentBar.low = bar.low


#Starts the Bot
bot = Bot()

