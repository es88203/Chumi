import tornado.ioloop
import tornado.web
import pymysql
import urllib.request
from tornado import websocket
 
 
 
clients = []

def decoder(msg):
    len_type = len("type=")
    len_name = len("name=")
    indx_type = msg.index("type=") + len_type
    indx_name = msg.index("name=") + len_name
    indx_spc1 = msg.index(" ")
    indx_spc2 = msg[indx_name:].index(" ") + indx_name
    typ = msg[indx_type:indx_spc1]
    name = msg[indx_name:indx_spc2]
    context = msg[indx_spc2+1:]
    return(typ, name, context)

def decoder2(msg):
    len_type = len("type=")
    len_name = len("name=")
    len_number = len("number=")
    len_imei = len("imei=")
    len_regID = len("regID=")

    indx_type = msg.index("type=") + len_type
    indx_name = msg.index("name=") + len_name
    indx_number = msg.index("number=") + len_number
    indx_imei = msg.index("imei=") + len_imei
    indx_regID = msg.index("regID=") + len_regID
	
    indx_spc1 = msg.index(" ")
    indx_spc2 = msg[indx_name:].index(" ") + indx_name
    indx_spc3 = msg[indx_number:].index(" ") + indx_number
    indx_spc4 = msg[indx_imei:].index(" ") + indx_imei
    #indx_spc5 = msg[indx_regID:].index(" ") + indx_regID
	
    typ = msg[indx_type:indx_spc1]
    name = msg[indx_name:indx_spc2]
    number = msg[indx_number:indx_spc3]
    imei = msg[indx_imei:indx_spc4]
    regID = msg[indx_spc4+7:]
    return(typ, name, number, imei, regID)
	
def sentHttp(title, msg, regID):
    url = 'http://140.127.218.105/noti_test2/sender.php'
    values = {'title':title, 'msg' : msg, 'regID': regID}
    data = urllib.parse.urlencode(values)
    data = data.encode('utf-8')
    req = urllib.request.Request(url, data)
    response = urllib.request.urlopen(req)
	
class connectMyDB:
    def refresh(self, name):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
        cur.execute("SELECT wait, store_info.call, total FROM store_info WHERE store_name=%s",name)
        r = cur.fetchall()

        wait = r[0][0]
        call = r[0][1]
        total = r[0][2]

        cur.execute("UPDATE store_info SET wait=%s, store_info.call=%s, total=%s WHERE store_name=%s",(wait, call, total, name))
        conn.commit()
		
        cur.close()
        conn.close()
		
        return(wait, call, total)

    def next(self, name):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
        cur.execute("SELECT wait, store_info.call, total FROM store_info WHERE store_name=%s",name)
        r = cur.fetchall()

        wait = r[0][0]
        call = r[0][1]
        total = r[0][2]
        wait = wait-1
        call = call+1

        cur.execute("UPDATE store_info SET wait=%s, store_info.call=%s, total=%s WHERE store_name=%s",(wait, call, total, name))
        conn.commit()
		
        cur.execute("SELECT GCM_regID FROM take_number, store_info WHERE take_number.store_number=store_info.store_number AND custom_number=%s AND isCalled=0 ",call)
        r = cur.fetchall()
        regID = r[0][0]
        #print(r[0][0])

        regID2 = -1
        regID3 = -1
		
        cur.execute("SELECT GCM_regID FROM take_number, store_info WHERE take_number.store_number=store_info.store_number AND custom_number=%s AND isCalled=0 ",call+1)
        r = cur.fetchall()
        if not r:
            print("Not exist next one!")
        else:
            if r[0][0]!="":
                regID2 = r[0][0]
				
        cur.execute("SELECT GCM_regID FROM take_number, store_info WHERE take_number.store_number=store_info.store_number AND custom_number=%s AND isCalled=0 ",call+2)
        r = cur.fetchall()
        if not r:
            print("Not exist next two!")
        else:
            if r[0][0]!="":
                regID3 = r[0][0]

		
        cur.close()
        conn.close()
		
        return(wait, call, total, regID, regID2, regID3)
		
    def add(self, name, num, imei, regID):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
        cur.execute("SELECT wait, store_info.call, total, store_number FROM store_info WHERE store_name=%s",name)
        r = cur.fetchall()
        wait = r[0][0]
        call = r[0][1]
        total = r[0][2]
        store_num = r[0][3]
		
        cur.execute("SELECT id FROM take_number WHERE store_number=%s AND isCalled=0 AND customer_IMEI=%s",(store_num, imei))
        r = cur.fetchone()
        if not r:	#該用戶沒抽過號
            wait = wait+1
            total = total+1
			
            cur.execute("UPDATE store_info SET wait=%s, total=%s WHERE store_name=%s",(wait, total, name))
            conn.commit()

            cur.execute("INSERT INTO take_number (store_number, customer_IMEI, custom_number, GCM_regID)VALUES (%s, %s, %s, %s)",(store_num, imei, total, regID) )
            conn.commit()
            succes = 1
        else:
            print("用戶-"+imei+"重覆取號")
            succes = 0
		
        cur.close()
        conn.close()
		
        return(wait, call, total, succes)

    def orderPay(self, storeName, context):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
		
        index = context.find("sum=")
        imei = context[5:index]
        index2 = context.find("order=")
        sum = context[index+4:index2]
        #print("SUM="+sum)
		
        cur.execute("SELECT id, GCM_regID, CustomerNum FROM take_number, store_info WHERE store_name=%s AND take_number.store_number=store_info.store_number AND customer_IMEI=%s AND isCalled=0 AND isOrdered=0",(storeName, imei) )
        try:
            r = cur.fetchall()
            takeID = r[0][0]
            RegId = r[0][1]
            CustomerNum = r[0][2]
            #print(CustomerNum)

            cur.execute("UPDATE take_number SET isOrdered=1 WHERE id=%s",(takeID))
            conn.commit()
			
            if CustomerNum == 0:
                cur.execute("UPDATE take_number SET CustomerNum=%s WHERE id=%s",(sum, takeID))
                conn.commit()
		
            #handle the context
            context = context[index2:]
            nowString = context[6:]
            while len(nowString)>0:
                index = nowString.find(" ")
                tmp = nowString[0:index]
                nowString= nowString[index+1:]
                index = tmp.find(":")
                name = tmp[0:index]
                amount = tmp[index+1:]
                #print(storeName)
                cur.execute("INSERT INTO orders (id, items, quantity, store_Name)VALUES (%s, %s, %s, %s)",(takeID, name, amount, storeName) )
                conn.commit()
                cur.execute("INSERT INTO orders_history (Hstry_id, Hstry_items, Hstry_quantity, Hstry_store_Name)VALUES (%s, %s, %s, %s)",(takeID, name, amount, storeName) )
                conn.commit()
                print("name:"+name+" amount:"+amount)
            success = 1;
        except:
            print("該客戶已點過餐了")
            success = 0;			
        cur.close()
        conn.close()
        return (success, RegId)
		
    def queue(self, imei):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
        cur.execute("SELECT custom_number, store_name, store_info.call FROM take_number, store_info WHERE isCalled=0 AND customer_IMEI=%s AND store_info.store_number = take_number.store_number",imei)
        try:
            r = cur.fetchall()
            GotNumber = r[0][0]
            name = r[0][1]
            call = r[0][2]
            return (name.decode("utf-8"), GotNumber, call)
        except:
            print("Queue fail")
            return (-1, 0, 0)	
		
    def init(self, name):
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='chumi_user', passwd='', db='ens', charset='utf8')
        cur = conn.cursor()
        cur.execute("UPDATE store_info SET wait=0, store_info.call=0, total=0 WHERE store_name=%s",name)
        conn.commit()
		
        cur.execute("SELECT store_number FROM store_info WHERE store_name=%s",name)
        r = cur.fetchall()
        store_num = r[0][0];
		
        cur.execute("UPDATE take_number SET isCalled=1 WHERE store_number=%s",store_num)
        conn.commit()
        #cur.execute("DELETE from take_number WHERE store_number=%s",store_num)
        #conn.commit()
		
        cur.execute("DELETE from orders WHERE store_Name=%s",name)
        conn.commit()
		
        cur.close()
        conn.close()
 
class ChatRoom(websocket.WebSocketHandler):
    def open(self):			#有人連上來
        clients.append(self)
        msg = "type=refresh sum=0 now=0"
        self.write_message(msg)
        print(str(id(self))+" Added")
        for client in clients:
            print (str(id(client)) + "   **");
    
    def on_close(self):		#有人斷線
        clients.remove(self)
        print (str(id(self))+" Exit")
        #for client in clients:
            #client.write_message(str(id(self)) + " 離開了")
    
    def on_message(self, message):
        (tpy,name,context)=decoder(message)
        print("receive: ",message)
        if tpy == "next":
            db = connectMyDB()
            (wait, call, total, regID, regID2, regID3)=db.next(name)
			
            msg = "type=update sum="+str(total)+" now="+str(call)
            for client in clients:
                client.write_message(msg)
            sentHttp("輪到你囉","現在輪到"+str(call)+"號了 歡迎光臨", regID)
            if regID2 != -1:
                sentHttp("快輪到你囉","提醒您 現在輪到"+str(call)+"號了", regID2)
            if regID3 != -1:
                sentHttp("快到你囉","提醒您 現在輪到"+str(call)+"號了", regID3)
        elif tpy == "add":
            print(message)
            (tpy, name, num, imei, regID)=decoder2(message)
            db = connectMyDB()
            (wait, call, total, succes)=db.add(name, num, imei, regID)
            
            if(succes==1):
                print("ADD: type:"+tpy+" name:"+name+" num:"+num+" IMEI:"+imei+" regID:"+regID)
                msg = "type=update sum="+str(total)+" now="+str(call)
                for client in clients:
                    client.write_message(msg)
                sentHttp("抽號成功","您的號碼是"+str(total)+"號 現在等待人數:"+str(total-call)+"人", regID)
        elif tpy == "refresh":
            db = connectMyDB()
            print("Decoder name is: "+name);
            (wait, call, total)=db.refresh(name)
            msg = "type=update sum="+str(total)+" now="+str(call)
            self.write_message(msg)
        elif tpy == "init":
            db = connectMyDB()
            db.init(name)
            msg = "type=update sum=0 now=0"
            for client in clients:
                client.write_message(msg)
            #sentHttp("商店重新開啟,人數歸零", "")
        elif tpy == "queue":
            (tpy, name, num, imei, regID)=decoder2(message)
            db = connectMyDB()
            (name, got, call) = db.queue(imei)
            if(name != -1):
                #data  = line.decode('utf8').split(',');
                data = "type=exist sum="+str(got)+" now="+str(call)+" name="+str(name);
                #data = data.decode('utf8');
                #msg = data[2].encode('utf8')
                self.write_message(data)
            else:
                self.write_message("type=null sum=0 now=0")
        elif tpy == "orderPay":		#name 為 cellphone's imei number
            db = connectMyDB();
            (success, regID) = db.orderPay(name, context)
            if(success == 1):
                sentHttp("點餐成功","我們正開始準備您的餐點", regID)
        #else:
            #for client in clients:
                #client.write_message("Got")
 
application = tornado.web.Application([
    (r"/", ChatRoom),
])
 
if __name__ == "__main__":
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()