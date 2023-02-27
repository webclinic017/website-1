import sqlite3 as sql
import json

class User:
    def create(sql):
        print("create")
        con = sql.connect('qtbot.db')
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS users")
        #Create users table  in db_web database
        sql ='''CREATE TABLE "users" (
            "UID"	INTEGER PRIMARY KEY AUTOINCREMENT,
            "UNAME"	TEXT,
            "CONTACT"	TEXT
        )'''
        cur.execute(sql)
        con.commit()
        con.close()

    def add_user(data,sql):
        uname=data['uname']
        contact=data['contact']
        con=sql.connect("qtbot.db")
        cur=con.cursor()
        cur.execute("insert into users(UNAME,CONTACT) values (?,?)",(uname,contact))
        con.commit()


    def select_user(sql):
        con=sql.connect("qtbot.db")
        con.row_factory=sql.Row
        cur=con.cursor()
        cur.execute("select * from users")
        data=cur.fetchall()
        res = json.dumps( [dict(ix) for ix in data] ) 
        
        return res
    
    def select_one(uid,sql):
        con=sql.connect("qtbot.db")
        con.row_factory=sql.Row
        cur=con.cursor()
        cur.execute("select * from users")
        data=cur.fetchall()
        return data

            
    def edit_user(uid,data,sql):
        uname=data['uname']
        contact=data['uname']
        con=sql.connect("qtbot.db")
        cur=con.cursor()
        cur.execute("update users set UNAME=?,CONTACT=? where UID=?",(uname,contact,uid))
        con.commit()
        
    def delete_user(uid):
        con=sql.connect("qtbot.db")
        cur=con.cursor()
        cur.execute("delete from users where UID=?",(uid,))
        con.commit()
       


