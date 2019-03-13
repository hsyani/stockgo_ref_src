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
        self.logger = TTlog(logger_name="Check_IfTRMakeOnReceiveRealDataHappen").logger
        self.mongo = MongoClient()
        self.cc_db = self.mongo.Check_IfTRMakeOnReceiveRealDataHappen
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
        code = "061970"
        self.rt_hoga_collector(code)

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

    def rt_hoga_collector_callback(self, data):
        curr_time = datetime.today()
        if curr_time < self.s_time:
            self.logger.info("=" * 100)
            self.logger.info("장 Open 전 입니다. 오전 9:00 이후에 검색된 정보에 대해서만 저장합니다.")
            self.logger.info("=" * 100)
            return

        self.logger.info("[rt_hoga_collector_callback called]")

        try:
            tablename = data["code"] + data["real_type"]
            dictdata = {}
            for fid in constant.RealType.REALTYPE[data["real_type"]]:
                value = self.kw._get_comm_real_data(data["code"], fid)
                self.logger.info(constant.RealType.REALTYPE[data["real_type"]][fid] + ": " + value)
                dictdata[constant.RealType.REALTYPE[data["real_type"]][fid]] = value
            self.cc_db[tablename].insert({
                "code": data["code"], "dictdata": dictdata
            })
        except:
            print("error occured while rt_hoga_collector_callback doing")

    def rt_hoga_collector(self, code):
        screen_no = "0111"
        self.logger.info("[rt_hoga_collector called]")

        # callback fn 등록
        self.kw.reg_callback("OnReceiveRealData", "", self.rt_hoga_collector_callback)

        self.kw.get_hoga_info(code, screen_no)


    def real_condi_search(self):
        self.logger.info("실시간 조건 검색 시작합니다.")
        # callback fn 등록
        self.kw.reg_callback("OnReceiveRealCondition", "", self.rt_hoga_collector)
        condi_info = self.kw.get_condition_load()

        condi_name = "52주1"
        condi_id = condi_info[condi_name]

        # 화면번호, 조건식이름, 조건식ID, 실시간조건검색(1)
        self.logger.info("화면번호: {}, 조건식명: {}, 조건식ID: {}".format(
            self.screen_no, condi_name, condi_id
        ))
        code_list = self.kw.send_condition(str(self.screen_no), condi_name, int(condi_id), 1)
        collection_name = condi_name + str(datetime.today().date())
        try:
            self.cc_db.create_collection(collection_name)
            self.cc_db[collection_name].create_index("code", unique=True)   # set unique index by code number
        except:
            self.logger.info("colletion name requested is exist already")

        for code in code_list:
            try:
                self.cc_db[collection_name].insert_one({"code": code})
            except pymongo.errors.DuplicateKeyError:
                self.logger.info("code already exist: {}".format(code))

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
