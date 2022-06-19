import base64
import json
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import List, Union
from urllib.error import HTTPError

from aqt import AnkiQt
from bs4 import BeautifulSoup, Tag
from .Config import Config
from .Exceptions import NoResultsException
from .Util import log_debug

search_url = 'https://korean.dict.naver.com/api3/koen/search?m=mobile&shouldSearchVlive=true&lang=en&query='


@dataclass
class Pronunciation:
	language: str
	user: str
	origin: str
	id: int
	votes: str
	download_url: str
	is_ogg: bool
	word: str
	mw: AnkiQt
	audio: Union[str, None] = None
	
	def download_pronunciation(self):
		from .. import temp_dir
		req = urllib.request.Request(self.download_url)
		#dl_path = os.path.join(temp_dir, "pronunciation_" + self.language + "_" + self.word + (".ogg" if self.is_ogg else ".mp3"))
		dl_path = os.path.join(temp_dir, self.download_url.split("/")[len(self.download_url.split("/"))-1].split('?')[0])
		with open(dl_path, "wb") as f:
			res: HTTPResponse = urllib.request.urlopen(req)
			f.write(res.read())
			res.close()
		
		media_name = self.mw.col.media.add_file(dl_path)
		self.audio = media_name
	
	def remove_pronunciation(self):
		self.mw.col.media.trash_files([self.audio])
		self.audio = None


def prepare_query_string(input: str, config: Config) -> str:
	query = str(input)
	query = query.strip()
	for char in config.get_config_object("replaceCharacters").value:
		query = query.replace(char, "")
	log_debug("[Naver.py] Using search query: %s" % query)
	return query


class Naver:
	def __init__(self, word: str, language: str, mw, config: Config):
		self.html = {}
		self.language = language
		self.word = prepare_query_string(word, config)
		self.pronunciations: List[Pronunciation] = []
		self.mw = mw
		
		opener = urllib.request.build_opener()
		opener.addheaders = [
			('Accept', '*/*'),
			('DNT', 1),
			('Host', 'ko.dict.naver.com'),
			('Cookie', 'nid_slevel=1; nid_enctp=1; nx_ssl=2'),
			('Accept-Language', 'en,ko-KR;q=0.9,ko;q=0.8,en-US;q=0.7'),
			('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36'),
			('Sec-Fetch-Mode', 'no-cors'),
			('Sec-Fetch-Site', 'same-site'),
			('Cache-Control', 'no-cache'),
			('upgrade-insecure-requests', 1)]
		urllib.request.install_opener(opener)
	
	def load_search_query(self):
		try:
			log_debug("[Naver.py] Reading result page")
			page = urllib.request.urlopen(search_url + urllib.parse.quote_plus(self.word)).read()
			log_debug("[Naver.py] Done with reading result page")
			
			self.html = json.loads(page.decode())
			return self
		except Exception as e:
			log_debug("[Naver.py] Exception: " + str(e))
			if isinstance(e, HTTPError):
				e: HTTPError
				if e.code == 404:
					raise NoResultsException()
			else:
				raise e
	
	def get_pronunciations(self):
		log_debug("[Naver.py] Going through all items")
		items = self.html['searchResultMap']['searchResultListMap']['WORD']['items']
		
		for item in items:
			for symbol in item['searchPhoneticSymbolList']:
				if symbol['symbolFile'] != '' and item['expEntry'].replace('<strong>', '').replace('</strong>', '') == self.word:
					subtitle = '[' + symbol['symbolValue'].replace('<strong>', '').replace('</strong>', '') + '] - ' + item['meansCollector'][0]['means'][0]['value'].split(',')[0]
					origin = ""
					id = 1
					vote_count = ""
					dl_url = symbol['symbolFile']
					is_ogg = True
					self.pronunciations.append(Pronunciation(self.language, subtitle, origin, id, vote_count, dl_url, is_ogg, self.word, self.mw))
		#if not self.pronunciations:
		#	raise NoResultsException()
		return self
	
	def download_pronunciations(self):
		for pronunciation in self.pronunciations:
			pronunciation.download_pronunciation()
		
		return self
	
	@staticmethod
	def cleanup():
		from .. import temp_dir
		for f in os.listdir(temp_dir):
			os.remove(os.path.join(temp_dir, f))
