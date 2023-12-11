#!/usr/bin/python3

import sys
import os.path
import bs4
import requests


if len(sys.argv) == 1:
    print("Please specify a file to convert to a Web Page, Complete on the commandline.")
    exit(1)
elif len(sys.argv) > 2:
    print("Please specify just one file to convert to a Web Page, Complete.")
    exit(1)

file_name = sys.argv[1]

if not os.path.exists(filename):
    print(f"The file '{filename}' does not exist.")
    exit(1)

file_handle = open(file_name, "r")

file_html = ''.join(file_handle)

file_bs4 = bs4.BeautifulSoup(markup=file_html, features='lxml')

img_tags = file_bs4.find_all("img", src=True)
script_tags = file_bs4.find_all("script", src=True)
link_tags = file_bs4.find_all("link", rel="stylesheet", href=True)

