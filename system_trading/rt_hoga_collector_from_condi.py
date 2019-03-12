# built-in module
import sys
import pdb
import os
from datetime import datetime

import pandas as pd
import time

# UI(PyQt5) module
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5 import uic
from PyQt5 import QtGui
from PyQt5.QtCore import pyqtSlot

from slacker import Slacker

from kiwoom.kw import Kiwoom
from kiwoom import constant
from config import config_manager
from util.tt_logger import TTlog
from util.slack import Slack

from database.db_manager import DBM
from pymongo import MongoClient
import pymongo
import random
from collections import defaultdict
from kiwoom.constant import KiwoomServerCheckTimeError
import multiprocessing

targetcondname = '52주2'
targetcondid = '005'

# main class
class CondiCollector(QMainWindow):
    def __init__(self):
        # todo : 장시작시간에 대한 예외처리 (SetRealReg) 하여, 장 종료되면 자동종료
        super().__init__()
        # self.setupUi(self)  # load app screen
        self.logger = TTlog(logger_name="RT_HogaCollect").logger
        self.mongo = MongoClient()
        self.cc_db = self.mongo.RTHogaCollector
        self.slack = Slack("none")
        self.kw = Kiwoom()
        self.login()

        # ready to search condi
        self.load_stock_info()
        t = datetime.today()
        self.s_time = datetime(t.year, t.month, t.day, 9, 0, 0)  # 장 시작시간, 오전9시
        self.db_docname = str(t.strftime("%Y%m%d"))

        # fake trading
        self.timer = None
        self.start_timer()

        # core function
        self.screen_no = 4001
        self.N1, self.N2 = 0, 10

        self.real_condi_search()

        #self.realtime_stream_hoga_from_codelist()

        # mongoDB 로 저장한 Collector 에 대해서 DBM 으로 처리 하는 부분
        # self.dbm = DBM('RTHogaCollector')
        # df = pd.DataFrame(self.dbm.get_real_condi_search_data(t, TARGETCOND))

        # sys.exit()


    def login(self):
        err_code = self.kw.login()
        if err_code != 0:
            self.logger.error("Login Fail")
            exit(-1)
        self.logger.info("Login success")

    def load_stock_info(self):
        self.stock_dict = {}
        doc = self.cc_db.stock_information.find({})
        for d in doc:
            code = d["code"]
            self.stock_dict[code] = d
        self.logger.info("loading stock_information completed.")

    def start_timer(self):
        if self.timer:
            self.timer.stop()
            self.timer.deletezzLater()
        self.timer = QTimer()
        self.timer.timeout.connect(self.fake_check_to_sell)
        # self.timer.setSingleShot(True)
        self.timer.start(1000) # 1 sec interval

    def fake_check_to_sell(self):
        """

        :return:
        """

    # 콜백 함수에 대한 콜백 함수 (3/6 검증 완료)
    def rt_hoga_collector(self, item_data):
        curr_time = datetime.today()
        if curr_time < self.s_time:
            self.logger.info("=" * 100)
            self.logger.info("장 Open 전 입니다. 오전 9:00 이후에 검색된 정보에 대해서만 저장합니다.")
            self.logger.info("=" * 100)
            return

        self.logger.info("[rt_hoga_collector called]")
        self.logger.info("data: {}".format(item_data))

        if item_data["real_type"] == "주식호가잔량":
            tablename = item_data["code"] + "hoga"
            self.cc_db[tablename].insert({
                'real_data' : item_data["real_data"]
            })
        elif item_data["real_type"] == "주식체결":
            tablename = item_data["code"] + "chegyul"
            self.cc_db[tablename].insert({
                'real_data': item_data["real_data"]
            })
        else:
            print("당신은 누구십니까 : " + item_data["code"] + item_data["real_type"] + " : " + item_data["real_data"])

        # self.cc_db[self.db_docname].insert({
        #                'date': curr_time,
        #                'real_data': item_data})

    def rt_item_collector(self, cond_data):
        screen_no = "6001"
        curr_time = datetime.today()

        self.logger.info("[rt_item_collector called]")
        # self.logger.info("data: {}".format(event_data))

        # 실시간 조건 검색으로 들어온 종목정보에 대해 DB 저장
        if cond_data["event_type"] == "I":
            self.cc_db.itemdectectrecord.insert({
                'date': curr_time,
                'code': cond_data["code"],
                #'stock_name': self.stock_dict[event_data["code"]]["stock_name"],
                #'market': self.stock_dict[event_data["code"]]["market"],
                'event': cond_data["event_type"],
                'condi_index': cond_data["condi_index"],
                'condi_name': cond_data["condi_name"]
            })
        # callback fn 등록
        self.kw.reg_callback("OnReceiveRealData", "", self.rt_hoga_collector)
        # [15] = 거래량 / [10] = 현재가 / [11] = 전일대비 / [12] = 등락율 / [228] = 체결강도 / [30] = 전일거래량대비(비율) / [31] = 거래회전율 / [12] = 등락율
        # 호가시간 / 매도호가 / 매도호가수량 / 매도호가직전대비 / 매수호가 / 매수호가수량
        # set_real_reg 등록시 마지막 파라미터를 1 로 설정하면 마지막에 추가된 종목만 추가되면서 수행됨
        # self.kw.set_real_reg(screen_no, data["code"], "21", 1)
        # self.kw.set_real_reg(screen_no, data["code"], "15;10;11;12;228;30;31;12", 1)
        # 60+9+9 개 fid
        self.kw.set_real_reg(screen_no, cond_data["code"], "15;10;11;12;228;30;31;12;21; \
                50;49;48;47;46;45;44;43;42;41;70;69;68;67;66;65;64;63;62;61;90;89;88;87;86;85;84;83;82;81; \
                51;52;53;54;55;56;57;58;59;60;71;72;73;74;75;76;77;78;79;80;91;92;93;94;95;96;97;98;99;100; \
                121;122;125;126;128;129;138;139;13", 1)

    def real_condi_search(self):
        self.logger.info("실시간 조건 검색 시작합니다.")
        # callback fn 등록
        self.kw.reg_callback("OnReceiveRealCondition", "", self.rt_item_collector)
        condi_info = self.kw.get_condition_load()

        #condi_info = {'노네임' : '003', '52주2' : '005'}
        #condi_info = { targetcondname : targetcondid }
        for condi_name, condi_id in list(condi_info.items())[self.N1:self.N2]:
            # 화면번호, 조건식이름, 조건식ID, 실시간조건검색(1)
            self.logger.info("화면번호: {}, 조건식명: {}, 조건식ID: {}".format(
                self.screen_no, condi_name, condi_id
            ))
            self.kw.send_condition(str(self.screen_no), condi_name, int(condi_id), 1)
            time.sleep(0.5)


# Print Exception Setting
sys._excepthook = sys.excepthook

def exception_hook(exctype, value, traceback):
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

if __name__ == "__main__":
    global app
    print("Start Application : " + sys.argv[0])
    app = QApplication(sys.argv)
    cc = CondiCollector()
    cc.show()
    sys.exit(app.exec_())
