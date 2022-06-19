import base64
import os
import re
import requests
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

search_url = "https://www.japanesepod101.com/learningcenter/reference/dictionary_post"


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
		dl_path = os.path.join(temp_dir, 'jp101a-' + self.word + '.mp3')
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
	log_debug("[JapanesePod101Alt.py] Using search query: %s" % query)
	return query


class JapanesePod101Alt:
	def __init__(self, word: str, language: str, mw, config: Config):
		self.html: BeautifulSoup
		self.language = language
		self.word = prepare_query_string(word, config)
		self.pronunciations: List[Pronunciation] = []
		self.mw = mw
		
		#opener = urllib.request.build_opener()
		#opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36')]
		#urllib.request.install_opener(opener)
	
	def load_search_query(self):
		try:
			log_debug("[JapanesePod101Alt.py] Reading result page")
			form_data = {'post': 'dictionary_reference', 'match_type': 'exact', 'search_query': self.word, 'vulgar': 'true'}
			req_head = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36'}
			page = requests.post(search_url, data = form_data, headers = req_head).text
			
			log_debug("[JapanesePod101Alt.py] Initializing BS4")
			self.html = BeautifulSoup(page, "html.parser")
			log_debug("[JapanesePod101Alt.py] Initialized BS4")
			return self
		except Exception as e:
			log_debug("[JapanesePod101Alt.py] Exception: " + str(e))
			if isinstance(e, HTTPError):
				e: HTTPError
				if e.code == 404:
					raise NoResultsException()
			else:
				raise e
	
	def get_pronunciations(self):
		log_debug("[JapanesePod101Alt.py] Going through all pronunciations")
		pronunciations: Tag = self.html.find_all(class_='dc-box--white dc-result-row')
		
		for pronunciation in pronunciations:
			subtitle = pronunciation.find(class_='dc-vocab_kana').get_text()
			origin = ""
			id = 1
			vote_count = ""
			dl_url = pronunciation.find(class_='dc-result-row__player-field').div.audio.source.get('src')
			is_ogg = True
			headword = self.word + ' (Alt)'
			self.pronunciations.append(Pronunciation(self.language, subtitle, origin, id, vote_count, dl_url, is_ogg, headword, self.mw))
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
