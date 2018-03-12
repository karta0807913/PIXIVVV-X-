from PIL import Image, ImageTk, ImageDraw, ImageFont
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog
import io
import threading
import time
import os.path
from os.path import basename
import urllib.request
import http.cookiejar
import http.cookies
import requests
import ssl
import json
import re
import ctypes
import cv2
import numpy as np
import socket

loginpage = 'http://www.pixiv.net/login.php/'
loginposturl = 'https://accounts.pixiv.net/api/login?lang=zh_tw'
hosturl = 'https://www.pixiv.net/'
searchUrl = 'https://www.pixiv.net/search.php'
limit = 4000
threadLines = 5
nowThreadLines = 0

def Mbox(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

def getKey(item):
	return item['book_num']

class Application(tk.Frame):
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.pack()
        self.login()
        self.createWidgets()
        self.imagesPerPage = 250
        self.makeViewIndex = 0
        self.resetMakeViewFunction = False
        self.makeViewIndexLock = threading.Lock()
        self.makeViewThreadNumLock = threading.Lock()
        self.maxImageThread = 3
        self.imageThreadNum = 0
        self.buttons = []
        self.illustList = []
        self.fileFloderName = ""
        self.haveNaxt = [False, False]
        self.tkImage = [ImageTk.PhotoImage(Image.new("RGBA", (240, 240), (255, 255, 255, 0)))] * self.imagesPerPage
        threading._start_new_thread(self.makeView, ())

    def canvasMouseWheelEvent(self, event) :
        if event.delta < 0:
            self.canvas.yview_scroll(3, tk.UNITS)
        else:
            self.canvas.yview_scroll(-3, tk.UNITS)
    def createWidgets(self):
        self.input          = tk.Entry(self) 
        self.input['width'] = 60
        self.input.grid(row=0, column=1, columnspan=6)

        self.searchButton = tk.Button(self)
        self.searchButton['text'] = 'search'
        self.searchButton.grid(row=0, column=8,)
        self.searchButton['command'] = lambda : self.searchStart()

        self.loadFileButton = tk.Button(self)
        self.loadFileButton['text'] = 'open from file'
        self.loadFileButton.grid(row=0, column=9,)
        self.loadFileButton['command'] = lambda : self.openFile()

        self.safeModeCheckButtonVar = tk.IntVar()
        self.safeModeCheckButton = tk.Checkbutton(self, variable=self.safeModeCheckButtonVar)
        self.safeModeCheckButton['text'] = 'safe mode'
        self.safeModeCheckButton.grid(row=7, column=8,)

        self.r18ModeCheckButtonVar  = tk.IntVar()
        self.r18ModeCheckButton = tk.Checkbutton(self, variable=self.r18ModeCheckButtonVar)
        self.r18ModeCheckButton['text'] = 'r-18 mode'
        self.r18ModeCheckButton.grid(row=8, column=8,)

        self.saveButton = tk.Button(self)
        self.saveButton['text'] = 'save images'
        self.saveButton.grid(row=8, column=1,)
        self.saveButton['command'] = lambda : threading._start_new_thread(self.saveAllImages, (frame.minBookNum.get(), ));
        
        self.minBookNumStringVar = tk.StringVar()
        self.minBookNumStringVar.trace('w', self.minBookNumTrace)

        self.minBookNum = tk.Entry(self, textvariable=self.minBookNumStringVar)
        self.minBookNum['width'] = 60
        self.minBookNum.grid(row=7, column=1,)

        self.nextPageButton = tk.Button(self)
        self.nextPageButton['text'] = ">>"
        self.nextPageButton['command'] = self.nextPage
        self.nextPageButton.grid(row=7, column=2)

        self.fontPageButton = tk.Button(self)
        self.fontPageButton['text'] = "<<"
        self.fontPageButton['command'] = self.fontPage
        self.fontPageButton.grid(row=7, column=0)

        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.grid(row=1, column=2, sticky='NS')
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=self.scrollbar.set, height=500)
        self.canvas.grid(row=1, column=1)

        self.bind("<MouseWheel>", self.canvasMouseWheelEvent)
        self.canvas.bind("<MouseWheel>", self.canvasMouseWheelEvent)
        self.scrollbar.config(command=self.canvas.yview)

        # reset the view
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = tk.Frame(self.canvas)
        interior_id = self.canvas.create_window(0, 0, window=interior,\
                                                anchor='nw')
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            self.canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != self.canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                self.canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior) #如果視窗大小變化

    def openFile(self) :
        if self.haveNaxt[1] == True :
            Mbox("Info", "Operation is not ended")
            return
        file = filedialog.askopenfilename(filetypes=(("Json files", "*.json"), ))
        if file == "":
            return

        self.makeViewIndexLock.acquire()
        try :
            self.illustList = json.load(open(file, 'rt', encoding='utf-8'))
        except :
            Mbox("Error", "this is not a json file", 0)
            self.makeViewIndexLock.release()
            return

        try:
            self.illustList[0]['artistName']
            self.illustList[0]['illustName']
            self.illustList[0]['illustNum']
            self.illustList[0]['smallImageFileName']
            self.illustList[0]['hugeImageFileName']
            self.illustList[0]['book_num']
            self.illustList[0]['illustUrl']
            self.illustList[0]['smallImgUrl']
        except NameError:
            Mbox("Error", "file error", 0)
            self.illustList=[]
            self.makeViewIndexLock.release()
            return
        self.makeViewIndexLock.release()
        self.input.delete(0, len(self.input.get()))
        self.input.insert(0, os.path.splitext(basename(file))[0])
        self._flushPage(1)

    def login(self):

        def makeOpener(head = {
            'Connection': 'Keep-Alive',
            'Accept': 'text/html, application/xhtml+xmlk, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
            'Referer':'http://www.pixiv.net/'
        }, cookiejar = http.cookiejar.CookieJar()):
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            handler = urllib.request.HTTPSHandler(context=context)
            opener = urllib.request.build_opener(handler, urllib.request.HTTPCookieProcessor(cookiejar))
            header = []
            for key, value in head.items():
                elem = (key, value)
                header.append(elem)
            opener.addheaders = header
            return opener

        #login to pixiv

        id = 'thisismyxxx24@gmail.com'
        passwd = '3d1e2aehky2qwfui20vz'

        loginList = {
            'return_to' : 'https://www.pixiv.net/',
            'pixiv_id' : id,
            'password' : passwd,
            'ref' : '',
            'source' : 'accounts',
            'captcha' : '',
            'g_recaptcha_response': '',
            'post_key' : ''
        }

        cj = http.cookiejar.CookieJar()
        self.opener = makeOpener(cookiejar=cj)
        res = self.opener.open(loginpage)
        soup = BeautifulSoup(res.read(), 'html.parser')
        find = soup.find('input', attrs = {'name' : 'post_key'})
        post_key = find.attrs['value']
        loginList['post_key'] = post_key

        postData = urllib.parse.urlencode(loginList).encode()
        self.opener.open(loginposturl, postData)

    def searchStart(self):
        searchStr = self.input.get()
        if not self.haveNaxt[1] and searchStr is not '':
            url = 'https://www.pixiv.net/search.php?word=' + urllib.parse.quote(searchStr) + '&order=date_d'
            if self.r18ModeCheckButtonVar.get() ^ self.safeModeCheckButtonVar.get() == 0:
                pass
            elif self.r18ModeCheckButtonVar.get() == 1:
                url += '&mode=r18'
                self.fileFloderName="_r18"
            elif self.safeModeCheckButtonVar.get() == 1:
                url += '&mode=safe'
                self.fileFloderName="_safe"

            self.haveNaxt[0] = True
            self.haveNaxt[1] = True
            self.illustList = []
            self._flushPage(1)
            threading._start_new_thread(self.makeillustList, (url, searchStr, ))
        
    def make_illust_list(self, imageItems, searchStr):
        searchStr = re.sub(r"[\\\*\?/|<>:\"\x00-\x1F]", "", searchStr)
        if (not(os.path.exists('./' + searchStr + self.fileFloderName + '/'))):
            os.makedirs('./' + searchStr + self.fileFloderName +'/')
        if (not(os.path.exists('./' + searchStr + self.fileFloderName + '/huge'))):
            os.makedirs('./' + searchStr + self.fileFloderName + '/huge')
    
        infos = json.loads(imageItems.find('input', id='js-mount-point-search-result-list')['data-items']);
        for info in infos:
        
            artistName          = info['userName']
            illustName          = info['illustTitle']
            illustNum           = info['illustId']
            filename            = re.sub(r"[\\\*\?/|<>:\"\x00-\x1F]", ".", artistName + '-' + illustName + '-' + str(illustNum) + '.jpg')
            smallImageFileName  = './'+ searchStr + self.fileFloderName +'/' + filename
            hugeImageFileName   = './' + searchStr + self.fileFloderName + '/huge/' + filename
            book_num            = info['bookmarkCount']
            smallImgUrl         = info['url']

            print(book_num)
            self.illustList.append(
                              {'artistName' : artistName,   'illustName'            : illustName,\
                               'illustNum'  : illustNum,    'smallImageFileName'    : smallImageFileName, 'hugeImageFileName' : hugeImageFileName, \
                               'book_num'   : book_num,     'illustUrl'             : 'http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustNum),
                               'smallImgUrl': smallImgUrl}
                )
                                                            #use thread to open it

    def makeillustList(self, url, searchStr):
        searchStr = self.input.get()
        response = None
        while True:
            while True:
                try:
                    response = self.opener.open(url, timeout=2)
                    soup = BeautifulSoup(response.read(), 'html.parser')
                    break;
                except :
                    continue

            self.make_illust_list(soup, searchStr)
            nextPage = soup.find('a', {'rel' : 'next'}, class_='_button')
            if nextPage is None :
                break
            url = searchUrl + nextPage['href']
        self.haveNaxt[0] = False

        while not self.haveNaxt[1]:
            time.sleep(1)
        self.illustList = sorted(self.illustList, key=getKey, reverse=True)
        f = open(searchStr + self.fileFloderName + '.json', 'wt', encoding='utf-8')
        s = json.dumps(self.illustList, ensure_ascii=False)
        f.write(s)
        f.close()
        i = 0
        print('sorting') #最後依照 book num 排序
        frame._flushPage(1)
        Mbox("OK", "Search Finish", 0)
        print('finish')
        self.haveNaxt[1] = False
        
    def minBookNumTrace(self, *args):
        self.minBookNumStringVar.set(re.sub(r'[^0-9]', '', self.minBookNumStringVar.get()))

    def nextPage(self):
        if self.imagesPerPage + self.makeViewIndex > len(self.illustList):
            Mbox("Info", "this is the last page", 0)
            return 

        self.makeViewIndexLock.acquire()
        self.canvas.yview_moveto(0)
        self.resetMakeViewFunction = True
        self.makeViewIndex += self.imagesPerPage
        self.makeViewIndexLock.release()

    def fontPage(self):
        if self.makeViewIndex - self.imagesPerPage < 0:
            Mbox("Info", "this is the home page", 0)
            return 

        self.makeViewIndexLock.acquire()
        self.canvas.yview_moveto(0)
        self.resetMakeViewFunction = True
        self.makeViewIndex -= self.imagesPerPage
        self.makeViewIndexLock.release()

    def setPage(self, pageIndex):
        if self.imagesPerPage * (pageIndex - 1) < 0 or self.imagesPerPage * (pageIndex - 1) > len(self.illustList) :
            Mbox("Info", "Error page index", 0)
            return
        if self.imagesPerPage * (pageIndex - 1) == self.makeViewIndex :
            return
        
        self.makeViewIndexLock.acquire()
        self.canvas.yview_moveto(0)
        self.resetMakeViewFunction = True
        self.makeViewIndex = self.imagesPerPage * (pageIndex - 1)
        self.makeViewIndexLock.release()

    def _flushPage(self, pageIndex) :
        if self.imagesPerPage * (pageIndex - 1) < 0 or self.imagesPerPage * (pageIndex - 1) > len(self.illustList) :
            Mbox("Info", "Error page index", 0)
            return
        
        self.makeViewIndexLock.acquire()
        self.canvas.yview_moveto(0)
        self.resetMakeViewFunction = True
        self.makeViewIndex = self.imagesPerPage * (pageIndex - 1)
        self.makeViewIndexLock.release()

    def makeView(self):

        def loadImages(illustinfo, index):
            if (not(os.path.isfile(illustinfo['smallImageFileName']))):
                arr = np.asarray(bytearray(self.opener.open(illustinfo['smallImgUrl']).read()), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                arr.tofile(illustinfo['smallImageFileName'])
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)
                d = ImageDraw.Draw(img)
                if len(img.mode) < 3 :
                    color=(255)
                else :
                    color=(255,0,0,0)
                d.text((img.width / 2, img.height/ 2 * 1.5), str(illustinfo['book_num']), fill=color, font=ImageFont.truetype("arial.ttf", size=40))
                del d
                self.tkImage[index] = ImageTk.PhotoImage(img)
                self.buttons[index]['image'] = self.tkImage[index]
            else:
                img = Image.open(illustinfo['smallImageFileName'])
                d = ImageDraw.Draw(img)
                if len(img.mode) < 3:
                    color=(255)
                else :
                    color=(255,0,0,0)
                d.text((img.width / 2, img.height/ 2 * 1.5), str(illustinfo['book_num']), fill=color, font=ImageFont.truetype("arial.ttf", size=40))
                del d
                self.tkImage[index] = ImageTk.PhotoImage(img)
                self.buttons[index]['image'] = self.tkImage[index]

            self.makeViewThreadNumLock.acquire()
            self.imageThreadNum -= 1
            self.makeViewThreadNumLock.release()

        i = 0
        while True:

            self.makeViewIndexLock.acquire()
            if self.resetMakeViewFunction :
                i = 0
                self.resetMakeViewFunction = False
            self.makeViewIndexLock.release()

            if self.imageThreadNum >= self.maxImageThread or not i < self.imagesPerPage or not i + self.makeViewIndex < len(self.illustList):
                time.sleep(0.2)
                continue

            #self.makeViewIndexLock.acquire()
            if i < len(self.buttons):
                self.buttons[i]['command'] = lambda illustInfo = self.illustList[i + self.makeViewIndex] : threading._start_new_thread(self.showImage, (illustInfo, ))
                if self.buttons[i]['image'] == '':
                    self.buttons[i]['image'] = self.tkImage[i]
            else:
                self.buttons.append(tk.Button(self.interior, height=200,
                                                width=200,
                                                image=self.tkImage[i],
                                                command=lambda illustInfo = self.illustList[i + self.makeViewIndex] : threading._start_new_thread(self.showImage, (illustInfo, ))))
                self.buttons[i].grid(row=int(i/5), column=i%5)
                self.buttons[i].bind("<MouseWheel>", self.canvasMouseWheelEvent)
                self.buttons[i].bind("<Button-3>", lambda event, illlustUrl=self.illustList[i + self.makeViewIndex]['illustUrl'] : self.cloneTextToClipboard(illlustUrl))

            self.makeViewThreadNumLock.acquire()
            self.imageThreadNum += 1
            threading._start_new_thread(loadImages, (self.illustList[i + self.makeViewIndex], i))
            self.makeViewThreadNumLock.release()

            #self.makeViewIndexLock.release()
            i = i + 1

    def cloneTextToClipboard(self, text) :
        self.clipboard_clear()
        self.clipboard_append(text)
        Mbox("ok", "cloned url", 0)

    def singalImage(self, findres):
        arr = np.asarray(bytearray(self.opener.open(findres['data-src']).read()), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img

    def showImage(self, illustInfo):
        filename = illustInfo['hugeImageFileName']
        if (not(os.path.isfile(filename))):
            response = self.opener.open('http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustInfo['illustNum']))
            soup = BeautifulSoup(response.read(), 'html.parser')
            findres = soup.find('img', class_='original-image')
            #normal image
            if findres is not None:
                img = self.singalImage(findres)
                cv2.imencode('.jpg', img)[1].tofile(filename)
                cv2.namedWindow(filename, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO);
                cv2.imshow(filename, img)
                cv2.waitKey(-1)
                return
            findres = soup.find('dev', class_='player toggle')
            #gif
            if findres is not None:
                Mbox("Sorry", "I can not show gif, illust id is " + str(illustInfo['illustNum']), 0)
                return
            #圖集
            i = 0
            try:
                response = self.opener.open('http://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(illustInfo['illustNum']))
            except urllib.error.HTTPError:
                Mbox("Sorry", "I can not show gif, illust id is " + str(illustInfo['illustNum']), 0)
                return 
            soup = BeautifulSoup(response.read(), 'html.parser')
            for url in soup.find_all('img', {'data-filter' : 'manga-image'}, class_='image ui-scroll-view'):
                if(i == 0):
                    fn=filename
                else:
                    fn = filename[0 : len(filename) - 4] + '-' + str(i) + filename[len(filename) - 4 : len(filename)] # <filename> - <str(i)> .jpg
                if (not (os.path.isfile(fn))):
                    arr = np.asarray(bytearray(self.opener.open(url['data-src']).read()), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    arr.tofile(fn)
                else :
                    img = cv2.imdecode(np.fromfile(fn, dtype=np.uint8), cv2.IMREAD_COLOR)

                cv2.namedWindow(fn, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO);  
                cv2.imshow(fn, img)
                cv2.waitKey(-1)
                i = i + 1
            return
        img = cv2.imdecode(np.fromfile(filename, dtype=np.uint8), cv2.IMREAD_COLOR)
        cv2.namedWindow(filename, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO);  
        cv2.imshow(filename, img)
        cv2.waitKey(-1)

    def saveAllImages(self, minBookNum):
        global limit
        global threadLines
        global nowThreadLines

        def saveImage(illustInfo):
            global nowThreadLines
            filename = illustInfo['hugeImageFileName']
            if (not(os.path.isfile(filename))):
                while True:
                    try:
                        response = self.opener.open('http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustInfo['illustNum']), timeout=4)
                        soup = BeautifulSoup(response.read(), 'html.parser')
                        break
                    except (urllib.error.URLError, socket.timeout) as e:
                        continue
                findres = soup.find('img', class_='original-image')

                if findres is not None:
                    img = self.singalImage(findres)
                    cv2.imencode('.jpg', img)[1].tofile(filename)
                    print("saving " + str(illustInfo['illustNum']))
                    nowThreadLines -= 1
                    return
                findres = soup.find('div', class_='player toggle')
                if findres is not None:
                    nowThreadLines -= 1
                    return
                i = 0
                try:
                    response = self.opener.open('http://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(illustInfo['illustNum']))
                except urllib.error.HTTPError:
                    return
                soup = BeautifulSoup(response.read(), 'html.parser')
                for url in soup.find_all('img', {'data-filter' : 'manga-image'}, class_='image ui-scroll-view'):
                    fn = filename[0 : len(filename) - 4] + '-' + str(i) + filename[len(filename) - 4 : len(filename)]
                    if (not (os.path.isfile(fn))):
                        arr = np.asarray(bytearray(self.opener.open(url['data-src']).read()), dtype=np.uint8)
                        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        cv2.imencode('.jpg', img)[1].tofile(fn)
                        print("saving " + str(illustInfo['illustNum']) + '-' + str(i))
                    i = i + 1
                nowThreadLines -= 1
                return
            nowThreadLines -= 1

        if minBookNum == "" or int(minBookNum) == 0 :
            Mbox("Error", "Please input book number", 0)
            return

        minBookNum = int(minBookNum)

        if self.haveNaxt[1] is True:
            Mbox("Error", "Operation has not ended", 0)
            return;
        self.haveNaxt[1] = True
        index = 0
        while index < limit and index < len(self.illustList) and self.illustList[index]['book_num'] > minBookNum:
            if nowThreadLines > threadLines:
                time.sleep(2)
            else:
                nowThreadLines += 1
                threading._start_new_thread(saveImage, (self.illustList[index],))
                index += 1
        Mbox("Successful", "Save All Images", 0);
        self.haveNaxt[1] = False

root = tk.Tk()
root.resizable(False,False)
frame = Application(master=root)
frame.mainloop()
