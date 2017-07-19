#!/usr/bin/env python
#-*- coding: utf-8 -*-
#pip install PalmDB-1.8.1

import re, os, time, sys, traceback, time
import logging, smtplib, argparse, sqlite3
import requests, shutil, tempfile
from kiehinen.ebook import Book
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


if os.environ.has_key('http_proxy'):
    os.environ.pop('http_proxy', '')

if os.environ.has_key('https_proxy'):
    os.environ.pop('https_proxy', '')


class MailServerConfig(object):
    def __init__(self, server, port=25):
        self.server = server
        self.port = port
        self.TLS = False
        self.username = None
        self.password = None


class Packtpub(object):
    def __init__(self, username, password, server, phantomjs_path, books_path, formato):
        self.username = username
        self.password = password
        self.server = server
        self.path = phantomjs_path
        self.wd = None
        self.today_book = None
        self.session = None
        self.books_path = books_path
        self.formato = formato




    def get_web_drive(self):
        if self.wd is None:
            # chromedriver='/home/~~~~/chromedriver'
            # os.environ["webdriver.chrome.driver"] = chromedriver
            # options = webdriver.ChromeOptions()
            # options.add_experimental_option("prefs", {
            #     "download.default_directory": r""+self.books_path,
            #     "download.prompt_for_download": False,
            #     "download.directory_upgrade": True,
            #     "safebrowsing.enabled": True
            # })
            #self.wd = webdriver.Chrome(chrome_options=options)
            brw_caps = dict(DesiredCapabilities.PHANTOMJS)
            brw_caps["phantomjs.page.settings.userAgent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 "
                "(KHTML, like Gecko) Chrome/15.0.87"
            )
            self.wd = webdriver.PhantomJS(executable_path=self.path,
                                        desired_capabilities=brw_caps)
            self.wd.set_window_size(1400,342)

        return self.wd

    def __get_session(self):
        if not self.session:
            if not self.is_logged():
                self.do_login()

            all_cookies = self.get_web_drive().get_cookies()

            if all_cookies:
                ### Para conseguir transferir a autenticação para o reques lib
                ### Preciso usar o mesmo User-Agent que o selenium usa
                agent = self.get_web_drive().execute_script("return navigator.userAgent")
                user_agent_hdr = {
                    'User-Agent': str(agent),
                }
                s = requests.Session()
                for cookie in all_cookies:
                    s.cookies.set(cookie['name'], cookie['value'])
                s.headers.update(user_agent_hdr)
                self.session = s

        return self.session


    def get_claim_url(self):
        browser = self.get_web_drive()
        claim_element = browser.find_element_by_class_name("dotd-main-book-form")
        return claim_element.find_element_by_tag_name('a').get_attribute("href")

    def is_logged(self):
        #When "div id=account-bar-login-register "is visible is not logging
        browser = self.get_web_drive()
        return not (browser.find_element_by_id("account-bar-login-register")).is_displayed();

    def do_login(self):
        logging.info("Verify if is logging")
        if not self.is_logged():
            logging.info("Not logged,  Try to login")
            browser = self.get_web_drive()
            div_login = browser.find_element_by_id('account-bar-login-register')
            pop_up = div_login.find_element_by_class_name('login-popup')
            pop_up.click()

            wait = WebDriverWait(browser, 300)
            wait.until(
                EC.visibility_of_element_located((By.ID, 'packt-user-login-form')))

            #packt-user-login-form
            #div id = account-bar-form
            # Getting campos
            form_login = browser.find_element_by_id('packt-user-login-form')
            username_field = form_login.find_element_by_id("email")
            password_field = form_login.find_element_by_id("password")
            build_id_field = form_login.find_element_by_name("form_build_id")
            form_id_field = form_login.find_element_by_name("form_id")
            login_btn = form_login.find_element_by_id("edit-submit-1")

            username_field.clear()
            password_field.clear()
            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            login_btn.click()

    def get_ebook(self, claim_url):
        # browser.find_element_by_xpath("//input[@value='Summary']").click()
        browser = self.get_web_drive()
        browser.get(claim_url)
        wait = WebDriverWait(browser, 300)
        raw_data = wait.until(
            EC.presence_of_element_located((By.ID, 'product-account-list')))


    def get_my_ebooks(self):
        browser = self.get_web_drive()
        conn = sqlite3.connect('livros.db')
        cursor = conn.cursor()
        for div in browser.find_elements_by_class_name("product-line"):
            try:
                eb_title = div.get_attribute("title")
                eb_id = div.get_attribute("nid")
                if eb_id:
                    cursor.execute(" SELECT * FROM livros where nid = ? and formato = ?", [eb_id, self.formato])
                    livro = cursor.fetchone()
                    if not livro:
                        logging.info("Try to download: " + eb_title)
                        filename = self.__download_file(url="https://www.packtpub.com/ebook_download/"+str(eb_id)+"/"+self.formato)
                        if filename:
                            logging.info("Downloaded: "+filename)
                            self.__add_to_catalog(id=eb_id, filename=filename, connection=conn)

                        else:
                            logging.info("Not found in this format: "+self.formato)

            except Exception, e:
                logging.error("Um erro foi encontrado: \n" + traceback.format_exc())
        browser.quit()
        conn.close()

    def __add_to_catalog(self, id, filename, connection):
        b = Book(os.path.join(self.books_path, filename))
        fname, _ = filename.split('.')
        cursor = connection.cursor()
        cursor.execute(" INSERT INTO livros (nid, nome, formato, filename) VALUES (?,?,?,?) ",
            [id, b.title, self.formato, fname])
        connection.commit()
        logging.info(filename+" was added in catalog")


    def __download_file(self,url):
        filename = None
        r = self.__get_session().get(url, stream=True)
        #browser.get("https://www.packtpub.com/ebook_download/"+str(eb_id)+"/"+format)
        if r.status_code == requests.codes.ok:
            file_size = int(r.headers['Content-Length'])
            if file_size <> 0:
                filename = self.__get_filename(r)
                logging.info("Download: "+filename)
                self.__save_file(response=r, filename=filename)

        return filename

    def __save_file(self, response, filename):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd,'w') as tmp:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, tmp)
            dst = os.path.join(self.books_path, filename)
            logging.debug("Save " + path + " in " + dst)
            shutil.move(path, dst)

    def __get_filename(self, response):
        filename = None
        if response.history:
            filename = re.search('.+/(.+\.mobi)\?.+',response.url).group(1)
        else:
            filename = re.search('.*filename\=\"(.+\.mobi)',
                response.headers['Content-disposition']).group(1)

        return filename

    def fetch_titles(self):
        conn = sqlite3.connect('livros.db')
        cursor = conn.cursor()
        folder = os.getcwd() + "/livros"
        lista=[]
        for file in os.listdir(folder):
            if file.endswith(".mobi"):
                [name, ext] = file.split(".")
                b = Book(folder+"/"+file)
                likename = b.title.replace(" ","%").replace("-","%").replace("'","%") + "%[eBook]%"
		logging.info("---")
		logging.info("Filename: "+file)
		logging.info("e-Book title: "+b.title)
		logging.info("SQL: SELECT nid FROM livros where formato='mobi' and nome like '"+likename+"';")
                cursor.execute('''SELECT nid FROM livros where formato=? and nome like ?''', ('mobi', likename))
                nid = cursor.fetchone()
                if nid:
                    print(b.title, name, str(nid[0]))
                    cursor.execute('''UPDATE livros SET nome = ?, filename=? WHERE nid=?''', (b.title, name, str(nid[0])))
                    conn.commit()
        conn.close()

    def get_today_book_title(self):
        browser = self.get_web_drive()
        #print browser.page_source
        #browser.save_screenshot("teste.png")
        div_title = browser.find_element_by_class_name('dotd-title')
        self.today_book = div_title.text

    def run(self):
        browser = self.get_web_drive()
        browser.get(self.server)
        self.get_today_book_title()
        logging.info("Book of the day is: "+self.today_book)
        claim_url = "https://www.packtpub.com/account/my-ebooks"
        ##self.get_claim_url()
        logging.info(claim_url)
        browser.get(claim_url)
        logging.info("Do login")
        self.do_login()
        logging.info("Logged in")
        logging.info("Trying to get the books")
        self.get_ebook(claim_url)
        self.get_my_ebooks()
        ##Para dar tempo dos downloads acabarem
        ## Só deve ser usado quando tem arquivos na pasta ainda não salvos no DB
	    #self.fetch_titles()


if __name__ == "__main__":
    PATH = os.getcwd() + "/phantomjs"
    books_path = os.path.join(os.getcwd(),"livros")


    parser = argparse.ArgumentParser(description="Packtpub my-book catalog")
    parser.add_argument('-e', '--email', required=True)
    parser.add_argument('-p', '--password', required=True)
    parser.add_argument('-P', '--phantom-path', default=PATH)
    parser.add_argument('-b', '--books-path', default=books_path)
    parser.add_argument('-f', '--format', default='mobi')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')




    packt = Packtpub(username=args.email,
                     password=args.password,
                     server="https://www.packtpub.com/packt/offers/free-learning",
                     phantomjs_path=args.phantom_path,
                     books_path=args.books_path,
                     formato=args.format)
    packt.run()