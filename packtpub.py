#!/usr/bin/env python
#-*- coding: utf-8 -*-

import re, os, time, sys
import logging, smtplib, argparse
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
    def __init__(self, username, password, server, phantomjs_path):
        self.username = username
        self.password = password
        self.server = server
        self.path = phantomjs_path
        self.wd = None
        self.today_book = None
        self.brw_caps = dict(DesiredCapabilities.PHANTOMJS)
        self.brw_caps["phantomjs.page.settings.userAgent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 "
            "(KHTML, like Gecko) Chrome/15.0.87"
        )

    def get_web_drive(self):
        if self.wd is None:
            self.wd = webdriver.PhantomJS(executable_path=self.path,
                                          desired_capabilities=self.brw_caps)
            self.wd.set_window_size(1400,342)
        return self.wd

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


    def verify_if_get(self):
        browser = self.get_web_drive()
        for div in browser.find_elements_by_class_name("product-line"):
            eb_title = div.get_attribute("title")
            logging.info(eb_title)
            if eb_title == self.today_book + " [eBook]":
                logging.info(eb_title + " - FOUND!!!")
                return True
        return False

    def get_today_book_title(self):
        browser = self.get_web_drive()
        #print browser.page_source
        #browser.save_screenshot("teste.png")
        div_title = browser.find_element_by_class_name('dotd-title')
        self.today_book = div_title.text

    def send_mail(self,to,smtp_config):
        import email
        msg = email.message_from_string(self.today_book)
        msg['From'] = "packtpub@dev-moodle.ml"
        msg['To'] = to
        msg['Subject'] = "New Book"

        smtpObj = smtplib.SMTP(smtp_config.server)
        smtpObj.port=smtp_config.port
        smtpObj.ehlo()

        if smtp_config.TLS:
            smtpObj.starttls()
            smtpObj.login(smtp_config.username, smtp_config.password)

        smtpObj.sendmail(sender, to, msg.as_string())
        logging.info("Successfully sent email")
        smtpObj.quit()

    def run(self):
        browser = self.get_web_drive()
        browser.get(self.server)
        self.get_today_book_title()
        logging.info("Book of the day is: "+self.today_book)
        claim_url = self.get_claim_url()
        logging.info(claim_url)
        browser.get(claim_url)
        logging.info("Do login")
        self.do_login()
        logging.info("Logged in")
        logging.info("Trying to get the book")
        self.get_ebook(claim_url)
        logging.info("Verifying if the book is on 'My Books'")

        if self.verify_if_get():
            self.today_book = "The book: "+self.today_book+" is in 'My Books' now"
            logging.info(self.today_book)
        else:
            self.today_book = "The book: "+self.today_book+" is not in your books"
            logging.warn(self.today_book)


if __name__ == "__main__":
    PATH = os.getcwd() + "/phantomjs"


    parser = argparse.ArgumentParser(description="Packtpub free book catcher")
    parser.add_argument('-e', '--email', default='')
    parser.add_argument('-p', '--password', default='')
    parser.add_argument('-P', '--phantom-path', default=PATH)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    #try:
    mail_config = MailServerConfig(server='smtp.live.com', port=587)
    mail_config.TLS = True
    mail_config.username="<YOUR account>"
    mail_config.password="<Your password>"


    packt = Packtpub(username=args.email,
                     password=args.password,
                     server="https://www.packtpub.com/packt/offers/free-learning",
                     phantomjs_path=args.phantom_path)
    packt.run()
    packt.send_mail(to='carlosalexandre@outlook.com',
                    smtp_config=mail_config)

    # except Exception, e:
    #     logging.fatal("Fatal Erro:"+ e.message + dir(e))






# print "pgpoolf2:"
# for s in server_lst:
#   [staus, connect_status] = get_connection_status(s,f1_status_data)
#   print s+"\t"+staus+"\t"+connect_status


# print browser.page_source
