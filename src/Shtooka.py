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

search_url = "https://shtooka.net/search.php?str="
download_url = "https://packs.shtooka.net/cmn-balm-hsk1/mp3/"


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
		"""Downloads the pronunciation using the pronunciation url in the pronunciation object, adds the audio to Anki's DB and stores the media id in the pronunciation object."""
		from .. import temp_dir
		req = urllib.request.Request(self.download_url)
		dl_path = os.path.join(temp_dir, "pronunciation_" + self.language + "_" + self.word + (
			".ogg" if self.is_ogg else ".mp3"))
		with open(dl_path, "wb") as f:
			res: HTTPResponse = urllib.request.urlopen(req)
			f.write(res.read())
			res.close()

		media_name = self.mw.col.media.add_file(dl_path)
		self.audio = media_name

	def remove_pronunciation(self):
		"""Removes the media file that was priorly downloaded"""
		self.mw.col.media.trash_files([self.audio])
		self.audio = None


def prepare_query_string(input: str, config: Config) -> str:
	query = str(input)  # clone
	query = query.strip()
	for char in config.get_config_object("replaceCharacters").value:
		query = query.replace(char, "")
	log_debug("[Shtooka.py] Using search query: %s" % query)
	return query


class Shtooka:
	def __init__(self, word: str, language: str, mw, config: Config):
		self.html: BeautifulSoup
		self.language = language
		self.word = prepare_query_string(word, config)
		self.pronunciations: List[Pronunciation] = []
		self.mw = mw

		# Set a user agent so that Shtooka/CloudFlare lets us access the page
		opener = urllib.request.build_opener()
		opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36')]
		urllib.request.install_opener(opener)

	def load_search_query(self):
		"""Loads the search result page on Shtooka"""
		try:
			log_debug("[Shtooka.py] Reading result page")
			page = urllib.request.urlopen(url=search_url + urllib.parse.quote_plus(self.word)).read()
			log_debug("[Shtooka.py] Done with reading result page")

			log_debug("[Shtooka.py] Initializing BS4")
			self.html = BeautifulSoup(page, "html.parser")
			log_debug("[Shtooka.py] Initialized BS4")
			return self
		except Exception as e:
			log_debug("[Shtooka.py] Exception: " + str(e))
			if isinstance(e, HTTPError):
				e: HTTPError
				if e.code == 404:
					raise NoResultsException()  # Interpret 404 http error code as no results found
			else:
				raise e  # otherwise, raise the exception as usual
	def get_pronunciations(self):
		"""Creates pronunciation objects from the soup"""
		log_debug("[Shtooka.py] Going through all pronunciations")
		pronunciations: Tag = self.html.find_all("div", class_="sound")
		
		log_debug("[Shtooka.py] Going through all pronunciations")
		for pronunciation in pronunciations:
			username = pronunciation.find("div", class_="sound_top").span.get_text().replace("\n", "").replace("\t", "")
			origin = ""
			id = 1
			vote_count = ""
			dl_url = pronunciation.find("div", class_="sound_top").find("div", class_="download").ul.find("a").get('href').replace("http://", "https://")
			is_ogg = True
			self.pronunciations.append(Pronunciation(self.language, username, origin, id, vote_count, dl_url, is_ogg, self.word, self.mw))
		return self

	def download_pronunciations(self):
		"""Downloads all pronunciations that are stored in the Shtooka class"""
		for pronunciation in self.pronunciations:
			pronunciation.download_pronunciation()
		
		return self

	@staticmethod
	def cleanup():
		"""Removes any files in the /temp directory."""
		from .. import temp_dir
		for f in os.listdir(temp_dir):
			os.remove(os.path.join(temp_dir, f))
