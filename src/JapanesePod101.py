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

search_url = "https://assets.languagepod101.com/dictionary/japanese/audiomp3.php"


@dataclass
class Pronunciation:
	language: str
	user: str
	origin: str
	id: int
	votes: str
	download_url: bytes
	is_ogg: bool
	word: str
	mw: AnkiQt
	audio: Union[str, None] = None
	
	def download_pronunciation(self):
		from .. import temp_dir
		#dl_path = os.path.join(temp_dir, "pronunciation_" + self.language + "_" + self.word + (".ogg" if self.is_ogg else ".mp3"))
		dl_path = os.path.join(temp_dir, 'jp101-' + self.word + '.mp3')
		with open(dl_path, "wb") as f:
			f.write(self.download_url)
		
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
	log_debug("[JapanesePod101.py] Using search query: %s" % query)
	return query


class JapanesePod101:
	def __init__(self, word: str, language: str, mw, config: Config, kana: str):
		self.html: bytes
		self.language = language
		self.word = prepare_query_string(word, config)
		self.pronunciations: List[Pronunciation] = []
		self.mw = mw
		self.kana = kana
		
		opener = urllib.request.build_opener()
		opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36')]
		urllib.request.install_opener(opener)
	
	def load_search_query(self):
		try:
			log_debug("[JapanesePod101.py] Reading result page")
			url = search_url + '?kanji=' + urllib.parse.quote_plus(self.word) + '&kana=' + urllib.parse.quote_plus(self.kana)
			self.html = urllib.request.urlopen(url).read()
			log_debug("[JapanesePod101.py] Done with reading result page")
			
			return self
		except Exception as e:
			log_debug("[JapanesePod101.py] Exception: " + str(e))
			if isinstance(e, HTTPError):
				e: HTTPError
				if e.code == 404:
					raise NoResultsException()
			else:
				raise e
	
	def get_pronunciations(self):
		log_debug("[JapanesePod101.py] Going through all pronunciations")
		
		if len(self.html) != 52288:
			subtitle = self.kana
			origin = ""
			id = 1
			vote_count = ""
			dl_url = self.html
			is_ogg = True
			self.pronunciations.append(Pronunciation(self.language, subtitle, origin, id, vote_count, dl_url, is_ogg, self.word, self.mw))
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
