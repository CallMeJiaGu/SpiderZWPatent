# -*- coding: utf-8 -*-
from lxml import etree
import requests
import time
import datetime
import codecs
import random
import MySQLdb as mdb
import sys
reload(sys)
sys.setdefaultencoding('utf8')


'''
在爬取知网的专利需要注意的是一个session只能请求几次大概10-15次左右，也就是说可以获取筛选条件超过了15页那么后面
的数据就拿不到，所以我们要保证每一次session请求的数据要尽量小于15页，可以采用增加筛选条件，比如领域、日期、省份，
这样可以保证每一次出来的数据都不是很多。
'''


# 用来初始化的类
class InitClass(object):
    # 获得时间段的函数
    def open_time(self,year_from, month_from, day_from, year_to, month_to, day_to):
        date_span = []
        start_date = datetime.date(year_from, month_from, day_from)
        stop_date = start_date + datetime.timedelta(days=3)
        date_span.append((str(start_date), str(stop_date)))
        end_date = datetime.date(year_to, month_to, day_to)
        while stop_date + datetime.timedelta(days=3) < end_date:
            start_date = stop_date + datetime.timedelta(days=1)
            stop_date = start_date + datetime.timedelta(days=3)
            date_span.append((str(start_date), str(stop_date)))
        date_span.append((str(stop_date+ datetime.timedelta(days=1)), str(end_date)))
        return date_span

    # 从数据库中得到学科分类代码
    def getSubjectCode(self):
        con_code = mdb.connect(host='10.1.13.29', user='root', passwd='tdlabDatabase', db='TechTradeTemp',
                               charset='utf8')
        cur_code = con_code.cursor()
        selectSQL = "SELECT subjectCode FROM `subjectSortCode`;"
        cur_code.execute(selectSQL)
        rows = cur_code.fetchall()
        subjectAreasCodes = []
        for each in rows:
            subjectAreasCodes.append(each[0])
        return subjectAreasCodes


class GetPatent(object):

    def __init__(self):
        initClass = InitClass()
        #self.subjectAreasCodes = initClass.getSubjectCode()
        self.subjectAreasCodes = ['B015']
        from_year = 2017
        from_month = 6
        from_day = 9
        to_year = 2017
        to_month = 6
        to_day = 16
        self.openDays = initClass.open_time(from_year,from_month,from_day,to_year,to_month,to_day)
        path_str = str(from_year) + '.' + str(from_month) + '.' + str(from_day) + "-" + str(to_year) + '.' + str(
            to_month) + '.' + str(to_day) + '.json'
        self.patentJson = codecs.open('target/' + path_str, mode='wb', encoding='utf-8', )
        self.badRequestFile = codecs.open('badRequest.txt', mode='wb', encoding='utf-8', )
        self.patentPrefixURL = 'http://dbpub.cnki.net/grid2008/dbpub/detail.aspx?dbcode=scpd&'

    def start_get(self):
        subject_areas_codes = self.subjectAreasCodes
        open_days = self.openDays
        for eachSubjectCode in subject_areas_codes:
            for eachOpenDay in open_days:
                print '当前学科领域代码为：', eachSubjectCode," 当前的爬取时间 %s %s" % (eachOpenDay[0], eachOpenDay[1])
                # 设置发送的请求的头
                headers = {
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, sdch",
                    "Accept-Language": "zh-CN,zh;q=0.8",
                    "Connection": "keep-alive",
                    "Host": "epub.cnki.net",
                    "Referer": "http://epub.cnki.net/kns/brief/result.aspx?dbprefix=SCPD",
                    "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36"
                }
                # 设置发送请求的参数
                times = time.strftime('%a %b %d %Y %H:%M:%S') + ' GMT+0800 (中国标准时间)'
                params = {
                    "action": "",
                    "NaviCode": eachSubjectCode,
                    "ua": "1.21",
                    "PageName": "ASP.brief_result_aspx",
                    "DbPrefix": "SCPD",
                    "DbCatalog": "中国专利数据库",
                    "ConfigFile": "SCPD.xml",
                    "db_opt": "中国专利数据库",
                    "db_value": "中国专利数据库",
                    "date_gkr_from": eachOpenDay[0],
                    "date_gkr_to": eachOpenDay[1],
                    "txt_1_sel": "GDM",
                    "txt_1_value1": "",
                    "txt_1_relation": "#CNKI_AND",
                    "txt_1_special1": "=",
                    "his": '0',
                    '__': times
                }
                home_page_url = 'http://epub.cnki.net/KNS/request/SearchHandler.ashx?'
                cn_session = self.getCnkiSession(home_page_url,headers,params)
                if cn_session is None:
                    self.badRequestFile.write(home_page_url+'\n'+eval(headers)+'\n'+eval(params))
                else:
                    for i in range(1,1000):
                        pageURL = 'http://epub.cnki.net/kns/brief/brief.aspx?curpage=%d&RecordsPerPage=50&QueryID=0&ID=&turnpage=1&tpagemode=L&dbPrefix=SCPD&Fields=&DisplayMode=listmode&PageName=ASP.brief_result_aspx' % i
                        tree = self.treeContentGet(cn_session,pageURL,i)
                        if tree is not None:
                            link = tree.xpath('//a[@class="fz14"]/@href')
                            print "该页有%d个专利" % len(link)
                            if len(link) == 0:
                                break
                            elif len(link) == 50 and i % 10 == 0:#知网在爬取的时候，针对一个cn_session只能拿到15页，所以要每隔14重新获得session
                                cn_session.close()#之前的session先关闭
                                cn_session = self.getCnkiSession(home_page_url, headers, params)
                            for j in range(len(link)):
                                index = link[j].find('filename')
                                pubNO = link[j][index + 9:]
                                self.patentJson.write(pubNO + '\n')
                        time.sleep(0.5)
                cn_session.close()


    # 获取有效的session,并且返回，没有获取记录下来
    def getCnkiSession(self,homepageURL,headers,params):
        cnkiSession = requests.Session()
        try_count = 0
        while try_count < 4:
            try:
                cnkiSession.get(homepageURL, headers=headers, params=params)
                return cnkiSession
            except BaseException:
                print "获取session异常，第" + str(try_count) + "次重试中。。。"
                sleep_time = random.randint(10, 20)
                time.sleep(sleep_time)
                try_count = try_count+1
        self.badRequestFile.write(self.badRequestFile + '\n' + eval(headers) + '\n' + eval(params))
        return None
    # 根据session 和 下标 获得对应的内容
    def treeContentGet(self,cnkiSession,pageURL,i):
        try_count = 0
        while try_count < 4:
            try:
                html = cnkiSession.get(pageURL).text
                print "第%d页请求成功" % i
                tree = etree.HTML(html)
                return tree
            except BaseException:
                print "第%d页连接异常" % i
                print "链接出现异常，等待第" + str(try_count) + "重试中。。。"
                time.sleep(random.randint(15, 16))
                try_count += 1
        return None


if __name__ == '__main__':
    getPatent = GetPatent()
    getPatent.start_get()
    getPatent.patentJson.close()

