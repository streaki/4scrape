#!/usr/bin/env python3

import os
import sys
import re
import json
import requests
import time
import html

def start():
    import getopt
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'mid:Mh', ['md5', 'ignore-case', 'dir=', 'directory=', 'multiline', 'help'])
    except getopt.GetoptError as e:
        print('Incorrect options used.', file=sys.stderr)
        display_usage(1)
    use_md5 = False
    ignore_case = False
    multiline = False
    directory = os.getcwd()
    for opt in opts:
        if   opt[0] in ['-m', '--md5']: use_md5 = True 
        elif opt[0] in ['-i', '--ignore-case']: ignore_case = True 
        elif opt[0] in ['-d', '--dir', '--directory']:
            if len(opt[1]) > 0 : directory = opt[1]
            if not os.path.isdir(directory):
                sys.exit('Invalid download directory!')
        elif opt[0] in ['-M', '--multiline']: multiline = True 
        elif opt[0] in ['-h', '--help']:
            display_usage()
    if len(args) < 2:   # 1: regex, 2: board
        print('Insufficient number of arguments.', file=sys.stderr)
        display_usage(1)
    regex = args[0]
    board = args[1]
    try:
        regex = re.compile(regex, 0|(re.IGNORECASE if ignore_case else 0)|(re.MULTILINE | re.DOTALL if multiline else 0))
        ScrapeInstance(board=board, regex=regex, use_md5=use_md5, directory=directory).walk()
    except re.error as e:
        print('Invalid regular expression (cannot be compiled)!', file=sys.stderr)
        sys.exit(1)

def display_usage(c=0):
    helptext = """
4scrape [-options] [--long-opts] regex board
    Searches the board specified for threads whose OP's title|comment conforms
    to the supplied regular expression, then scrapes images/media from these
    threads and saves them on disk. Done using the 4chan API.
    regex: The regular expression to search for. Example: 'YLYL'
    board: The board on 4chan to search on. Example: 'wsg'
-d/dir/ | --dir=/dir/ | --directory=/dir/
    The directory to save files to. If none specified, current working direc-
    tory is used.
-i | --ignore-case
    Makes the regular expression case-insensitive. Useful for looking for key-
    words actual humans write.
-M | --multiline
    Makes the regular expression multiline, and makes dot (.)match start/end of
    line. May be useful when looking for multiple keywords accross a post.
-m | --md5
    Builds a dictionary of MD5 hashes as files are downloaded, and saves them
    to a file once finished. File contents will be loaded into the dictionary
    when the script is next ran with the same board/working directory combina-
    tion with this option enabled. Prevents downloading of duplicate images
    accross different 4chan threads at a cost of loading an increasingly large
    dictionary and checking hashes for each file.
    (download of the same file within the same thread is prevented by a thread-
    specific metafile that contains the number of the most recent post in the
    thread - earlier posts are not checked for files)
-h | --help
    Displays this help text. Whether this indeed helps or not is up for debate.
"""
    if c==0:
        print(helptext)
    else:
        print(helptext, file=sys.stderr)
    sys.exit(c)

class ScrapeInstance:
    def __init__(self, board='g', regex=re.compile('python'), use_md5=False, directory=os.getcwd()):
        self.board      = board
        self.regex      = regex
        self.use_md5    = use_md5
        self.directory  = directory
        self.req        = Requester(1.0)
        if use_md5:
            self.md5path = f'{self.directory}/.md5'
            if os.path.isfile(self.md5path):
                with open(self.md5path, 'r') as md5file:
                    self.md5index = {m.rstrip() for m in md5file}
            else:
                self.md5index = set()

    def walk(self):
        print(time.asctime(time.localtime()))
        catalog = self.req.get(f'https://a.4cdn.org/{self.board}/catalog.json')
        if catalog.status_code // 100 != 2:
            return False
        catalog = json.loads(catalog.content)
        threads = []
        for page in catalog:
            for thread in page['threads']:
                if self.check_thread(self.regex, thread):
                    threads.append(thread['no'])
        print(threads)
        for no in threads:
            self.scrape(no)

    def scrape(self, no):
        thread = self.req.get(f'https://a.4cdn.org/{self.board}/thread/{no}.json')
        if thread.status_code // 100 != 2:
            return False
        thread = json.loads(thread.content)
        queue = []
        meta_path = f'{self.directory}/.{str(no)}'
        lastpost = 0
        if not os.path.isfile(meta_path):
            with open(meta_path, 'w') as meta_file:
                meta_file.write('0')
        else:
            with open(meta_path, 'r') as meta_file:
                try:
                    lastpost = int(meta_file.readline())
                except ValueError as e:
                    print(f'Invalid metafile for thread #{str(no)}', file=sys.stderr)
                    lastpost = 0
        if thread['posts'][-1]['no'] <= lastpost:
            return
        for post in thread['posts']:
            if (post['no'] > lastpost):
                try:
                    dl = True
                    if self.use_md5:
                        if post['md5'] in self.md5index:
                            dl = False
                    api_filename = f'{post["tim"]}{post["ext"]}'
                    filename = f'{post["tim"]}_{post["filename"]}{post["ext"]}'
                    if dl:
                        fil = self.req.get(f'https://i.4cdn.org/{self.board}/{api_filename}')
                        if fil.status_code // 100 == 2:
                            with open(self.directory + '/' + filename, 'wb') as pic:
                                pic.write(fil.content)
                                print(filename, 'saved.')
                    else:
                        print(filename, f'omitted: MD5 hash already in index ( {post["md5"]} ).' )
                    if self.use_md5:
                        if dl:
                            self.md5index.add(post['md5'])
                            with open (self.md5path, 'a') as md5file:
                                md5file.write(post['md5'] + '\n')
                except KeyError as e:
                    pass  # this happens when there's no pic attached to the post
        with open(meta_path, 'w') as meta_file:
            meta_file.write(str(thread['posts'][-1]['no']))

    def check_thread(self, regex, thread):
        res = None
        try:
            res = regex.search(thread['sub'])
        except KeyError as e:
            pass  # not every thread has a title
        try:
            if res == None:
                res = regex.search(html.unescape(thread['com']))
        except KeyError as e:
            pass  # not sure if it's possible to post a thread without a comment body, better to be on the safe side though
        #if res != None:
            #print(res)
        return res != None

class Requester:
    """Wrapper for HTTP(S) requests.

    * Keeps track of the request interval and time between requests - 4chan API specification
    mentions that you should not make more than 1 request/second lest you get b& for a day or so.
    The request interval can be tinkered with if you feel cocky.
    * Handles requests with the interval in mind and returns the response to calling function."""
    def __init__(self, interval):
        self.interval = interval
        self.last_req_time = time.time() - 1

    def get(self, address):
        since_last_req = time.time() - self.last_req_time
        if since_last_req < self.interval:
            time.sleep(self.interval - since_last_req)
        self.last_req_time = time.time()
        res = requests.get(address)
        if res.status_code // 100 != 2:
            print_error_status(res)
        return res

    def print_error_status(req):
        # TODO
        pass

if __name__ == "__main__":
    start()

