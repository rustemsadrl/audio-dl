import base64
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

search_url = "https://krdict.korean.go.kr/eng/dicSearchDetail/searchDetailWordsResult?nation=eng&nationCode=6&searchFlag=Y&sort=C&currentPage=1&ParaWordNo=&syllablePosition=&actCategoryList=&all_gubun=ALL&gubun=W&gubun=P&gubun=E&all_wordNativeCode=ALL&wordNativeCode=1&wordNativeCode=2&wordNativeCode=3&wordNativeCode=0&all_sp_code=ALL&sp_code=1&sp_code=2&sp_code=3&sp_code=4&sp_code=5&sp_code=6&sp_code=7&sp_code=8&sp_code=9&sp_code=10&sp_code=11&sp_code=12&sp_code=13&sp_code=14&sp_code=27&all_imcnt=ALL&imcnt=1&imcnt=2&imcnt=3&imcnt=0&all_multimedia=ALL&multimedia=P&multimedia=I&multimedia=V&multimedia=A&multimedia=S&multimedia=N&searchSyllableStart=&searchSyllableEnd=&searchOp=AND&searchTarget=word&searchOrglanguage=all&wordCondition=wordSame&query="


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
		dl_path = os.path.join(temp_dir, self.download_url.split("/")[len(self.download_url.split("/"))-1])
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
	log_debug("[krdict.py] Using search query: %s" % query)
	return query


class Krdict:
	def __init__(self, word: str, language: str, mw, config: Config):
		self.html: BeautifulSoup
		self.language = language
		self.word = prepare_query_string(word, config)
		self.pronunciations: List[Pronunciation] = []
		self.mw = mw
		
		opener = urllib.request.build_opener()
		opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36')]
		urllib.request.install_opener(opener)
	
	def load_search_query(self):
		try:
			log_debug("[krdict.py] Reading result page")
			page = urllib.request.urlopen(url=search_url + urllib.parse.quote_plus(self.word)).read()
			log_debug("[krdict.py] Done with reading result page")
			
			log_debug("[krdict.py] Initializing BS4")
			self.html = BeautifulSoup(page, "html.parser")
			log_debug("[krdict.py] Initialized BS4")
			return self
		except Exception as e:
			log_debug("[krdict.py] Exception: " + str(e))
			if isinstance(e, HTTPError):
				e: HTTPError
				if e.code == 404:
					raise NoResultsException()
			else:
				raise e
	
	def get_pronunciations(self):
		log_debug("[krdict.py] Going through all pronunciations")
		pronunciations: Tag = self.html.find_all("span", class_="search_sub")
		
		for pronunciation in pronunciations:
			links = pronunciation.find_all("a")
			for link in links:
				link.span.clear()
				subtitle = link.find_previous().get_text().strip() + ' - ' + link.find_parent().find_parent().find_parent().dd.get_text().replace('1.', '').strip().split(';')[0]
				origin = ""
				id = 1
				vote_count = ""
				dl_url = link.get('href').replace('javascript:fnSoundPlay(\'', '').replace('\');', '')
				is_ogg = True
				self.pronunciations.append(Pronunciation(self.language, subtitle, origin, id, vote_count, dl_url, is_ogg, self.word, self.mw))
		if not self.pronunciations:
			raise NoResultsException()
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
