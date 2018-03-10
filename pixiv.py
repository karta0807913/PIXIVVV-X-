from PIL import Image, ImageTk, ImageDraw, ImageFont
from bs4 import BeautifulSoup
import tkinter as tk
import io
import threading
import time
import os.path
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
haveNaxt = [False, False]
limit = 4000
threadLines = 5
nowThreadLines = 0
minBookNum = 250
illustList = []
images  = []
TkImage = []
buttons = []
globalStr = ''

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

def Mbox(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

def checkFileName(string):
    illegalChar = ['/', ':', '*', '?', '"', '<', '>', '|', '\\', \
                   '\n', '\t', '\\x', '\\u']
    iterator = 0
    length = len(string)
    while iterator < length:
        if string[iterator] in illegalChar:
            string = string[0:iterator] + ';' + string[iterator + 1:len(string)]
        iterator = iterator + 1
    return string

def make_illust_list(imageItems, illustList, searchStr):
    searchStr = checkFileName(searchStr)
    if (not(os.path.exists('./' + searchStr + '/'))):
        os.makedirs('./' + searchStr +'/')
    if (not(os.path.exists('./' + searchStr + '/huge'))):
        os.makedirs('./' + searchStr + '/huge')
    
    infos = json.loads(imageItems.find('input', id='js-mount-point-search-result-list')['data-items']);
    for info in infos:
        
        artistName          = info['userName']
        illustName          = info['illustTitle']
        illustNum           = info['illustId']
        filename            = re.sub(r"[\\\*\?/|<>:\"\x00-\x1F]", ".", artistName + '-' + illustName + '-' + str(illustNum) + '.jpg')
        smallImageFileName  = './'+ searchStr +'/' + filename
        hugeImageFileName   = './' + searchStr + '/huge/' + filename
        book_num            = info['bookmarkCount']
        smallImgUrl         = info['url']

        print(book_num)
        illustList.append({'artistName' : artistName,   'illustName'    : illustName,\
                           'illustNum'  : illustNum,    'smallImageFileName' : smallImageFileName, 'hugeImageFileName' : hugeImageFileName, \
                           'book_num'   : book_num,     'illustUrl'     : 'http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustNum),
                           'smallImgUrl': smallImgUrl})
                                                        #use thread to open it
def getKey(item):
	return item['book_num'] 

def searchStart(searchStr, haveNaxt, limit, buttons):
    if not haveNaxt[1] and searchStr is not '':
        url = 'http://www.pixiv.net/search.php?word=' + urllib.parse.quote(searchStr) + '&order=date_d'
        haveNaxt[0] = True
        haveNaxt[1] = True
        global globalStr
        global illustList
        global images
        global TkImage
        globalStr = searchStr
        illustList = []
        images  = []
        TkImage = []
        threading._start_new_thread(makeillustList, (haveNaxt, url, images, TkImage, buttons, searchStr, ))
        threading._start_new_thread(loadImages, (limit, images, ))
        threading._start_new_thread(makeView, (limit, frame, images, buttons, TkImage, searchStr, ))

class Application(tk.Frame):
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.pack()
        self.createWidgets()
        
        
    def minBookNumTrace(self, *args):
        self.minBookNumStringVar.set(re.sub(r'[^0-9]', '', self.minBookNumStringVar.get()))

    def createWidgets(self):
        self.input        = tk.Entry(self) 
        self.input['width'] = 60
        self.input.grid(row=0, column=0, columnspan=6)

        self.searchButton = tk.Button(self)
        self.searchButton['text'] = 'search'
        self.searchButton.grid(row=0, column=7,)

        self.saveButton = tk.Button(self)
        self.saveButton['text'] = 'save'
        self.saveButton.grid(row=8, column=0,)
        
        self.minBookNumStringVar = tk.StringVar()
        self.minBookNumStringVar.trace('w', self.minBookNumTrace)

        self.minBookNum = tk.Entry(self, textvariable=self.minBookNumStringVar)
        self.minBookNum['width'] = 60
        self.minBookNum.grid(row=7, column=0,)

        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.grid(row=1, column=1, sticky='NS')
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=self.scrollbar.set, height=500)
        self.canvas.grid(row=1, column=0)
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

def makeillustList(haveNaxt, url, images, TkImage, buttons, searchStr):
    global illustList
    response = None
    while True:
        while True:
            try:
                response = opener.open(url, timeout=2)
                soup = BeautifulSoup(response.read(), 'html.parser')
                break;
            except:
                continue

        make_illust_list(soup, illustList, searchStr)
        nextPage = soup.find('a', {'rel' : 'next'}, class_='_button')
        if nextPage is None :
            break
        url = searchUrl + nextPage['href']
    haveNaxt[0] = False

    while not haveNaxt[1]:
        time.sleep(1)
    illustList = sorted(illustList, key=getKey, reverse=True)
    f = open(searchStr + '.txt', 'wt', encoding='utf-8')
    s = json.dumps(illustList, ensure_ascii=False)
    f.write(s)
    f.close()
    i = 0
    print('sorting')
    while i < len(images):
        if (not(os.path.isfile(illustList[i]['smallImageFileName']))):
            byteIO = io.BytesIO(opener.open(illustList[i]['smallImgUrl']).read());
            images[i] = (Image.open(byteIO))
            images[i].convert('RGBA')
            images[i].save(illustList[i]['smallImageFileName'])
            d = ImageDraw.Draw(images[i])
            d.text((images[i].width / 2, images[i].height/ 2 * 1.5), str(illustList[i]['book_num']), fill=(255,0,0,0), font=ImageFont.truetype("arial.ttf", size=40))
            del d
            byteIO.close()
        else:
            images[i] = (Image.open(illustList[i]['smallImageFileName']))
            d = ImageDraw.Draw(images[i])
            d.text((images[i].width / 2, images[i].height/ 2 * 1.5), str(illustList[i]['book_num']), fill=(255,0,0,0), font=ImageFont.truetype("arial.ttf", size=40))
            del d
        img = ImageTk.PhotoImage(images[i])
        while i >= len(TkImage) :
            time.sleep(0.5)
        TkImage[i] = (img)
        buttons[i]['image'] = TkImage[i]
        buttons[i]['command'] = lambda k = i: threading._start_new_thread(showImage, (illustList[k],))
        images[i].close()
        i = i + 1
    
    Mbox("OK", "Search Finish", 0)
    print('finish')
    haveNaxt[1] = False

def singalImage(findres):
    arr = np.asarray(bytearray(opener.open(findres['data-src']).read()), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def loadImages(limit, images):
    global illustList
    i = 0
    while i < limit:
        while not i < len(illustList):
            if not haveNaxt[0]:
                return
            time.sleep(0.2)
        if (not(os.path.isfile(illustList[i]['smallImageFileName']))):
            arr = np.asarray(bytearray(opener.open(illustList[i]['smallImgUrl']).read()), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            arr.tofile(illustList[i]['smallImageFileName'])
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            d = ImageDraw.Draw(img)
            d.text((img.width / 2, img.height/ 2 * 1.5), str(illustList[i]['book_num']), fill=(255,0,0,0), font=ImageFont.truetype("arial.ttf", size=40))
            del d
            images.append(img)
        else:
            img = Image.open(illustList[i]['smallImageFileName'])
            d = ImageDraw.Draw(img)
            d.text((img.width / 2, img.height / 2 * 1.5), str(illustList[i]['book_num']), fill=(255,0,0,0), font=ImageFont.truetype("arial.ttf", size=40))
            del d
            images.append(img)
        i = i + 1

def saveImage(illustInfo):
    global globalStr
    global nowThreadLines
    filename = illustInfo['hugeImageFileName']
    if (not(os.path.isfile(filename))):
        while True:
            try:
                response = opener.open('http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustInfo['illustNum']), timeout=4)
                soup = BeautifulSoup(response.read(), 'html.parser')
                break
            except (urllib.error.URLError, socket.timeout) as e:
                continue
        findres = soup.find('img', class_='original-image')

        if findres is not None:
            img = singalImage(findres)
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
            response = opener.open('http://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(illustInfo['illustNum']))
        except urllib.error.HTTPError:
            return
        soup = BeautifulSoup(response.read(), 'html.parser')
        for url in soup.find_all('img', {'data-filter' : 'manga-image'}, class_='image ui-scroll-view'):
            fn = filename[0 : len(filename) - 4] + '-' + str(i) + filename[len(filename) - 4 : len(filename)]
            if (not (os.path.isfile(fn))):
                arr = np.asarray(bytearray(opener.open(url['data-src']).read()), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                cv2.imencode('.jpg', img)[1].tofile(fn)
                print("saving " + str(illustInfo['illustNum']) + '-' + str(i))
            i = i + 1
        nowThreadLines -= 1
        return
    nowThreadLines -= 1

def saveAllImages(minBookNum):
    global haveNaxt
    global illustList
    global limit
    global threadLines
    global nowThreadLines

    if minBookNum == "" or int(minBookNum) == 0 :
        Mbox("Error", "Please input book number", 0)
        return

    minBookNum = int(minBookNum)

    if haveNaxt[1] is True:
        return;
    haveNaxt[1] = True
    index = 0
    while index < limit and index < len(illustList) and illustList[index]['book_num'] > minBookNum:
        if nowThreadLines > threadLines:
            time.sleep(2)
        else:
            nowThreadLines += 1
            threading._start_new_thread(saveImage, (illustList[index],))
            index += 1
    Mbox("Successful", "Save All Images", 0);
    haveNaxt[1] = False

def showImage(illustInfo):
    global globalStr
    filename = illustInfo['hugeImageFileName']
    if (not(os.path.isfile(filename))):
        response = opener.open('http://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(illustInfo['illustNum']))
        soup = BeautifulSoup(response.read(), 'html.parser')
        findres = soup.find('img', class_='original-image')
        #normal image
        if findres is not None:
            img = singalImage(findres)
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
            response = opener.open('http://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(illustInfo['illustNum']))
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
                arr = np.asarray(bytearray(opener.open(url['data-src']).read()), dtype=np.uint8)
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

def makeView(limit, frame, images, buttons, TkImage, searchStr):
    global illustList
    i = 0
    while i < limit:
        while not i < len(illustList):
            if not haveNaxt[0]:
                return
            time.sleep(0.2)

        while not i < len(images):
            time.sleep(0.2)

        TkImage.append(ImageTk.PhotoImage(images[i]))
        if i < len(buttons):
            buttons[i]['image'] = TkImage[i]
            buttons[i]['command'] = lambda k = i: threading._start_new_thread(showImage, (illustList[k], ))
        else:
            buttons.append(tk.Button(frame.interior, height=200,
                                           width =200,
                                           image = TkImage[i],
                                           command=lambda k = i: threading._start_new_thread(showImage, (illustList[k], ))))
            buttons[i].grid(row=int(i/5), column=i%5)

        images[i].close()
        i = i + 1

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
opener = makeOpener(cookiejar=cj)
res = opener.open(loginpage)
soup = BeautifulSoup(res.read(), 'html.parser')
find = soup.find('input', attrs = {'name' : 'post_key'})
post_key = find.attrs['value']
loginList['post_key'] = post_key

postData = urllib.parse.urlencode(loginList).encode()
opener.open(loginposturl, postData)

root = tk.Tk()
root.resizable(False,False)
frame = Application(master=root)
frame.searchButton['command'] = lambda : searchStart(frame.input.get(), haveNaxt, limit, buttons,)
frame.saveButton['command'] = lambda : threading._start_new_thread(saveAllImages, (frame.minBookNum.get(), ));
frame.mainloop()
