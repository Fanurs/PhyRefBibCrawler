from datetime import datetime
import re
import urllib
import xmltodict

import bibtexparser as bp
from bs4 import BeautifulSoup as bs
from fuzzywuzzy import fuzz

# utilities
_doi_regex = re.compile(r'(10.(\d)+/(\S)+)')
_author_initial_spacing_regex = re.compile(r'(?<=([A-Z]|\.))([A-Z])')

def extract_doi(string):
    return _doi_regex.search(string)



class SingleRequest:
    def __init__(self, url):
        self.url = url
        self.doi = None
        self.headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36',
        }

        # clean up the url
        index = self.url.find('?casa_token=')
        if index > -1:
            self.url = self.url[:index]

        # in case where doi already presented in url, directly extract it
        if 'doi.org' in self.url:
            self.doi = extract_doi(self.url).group(1)
        
        # arxiv
        self.arxiv = False
        if 'arxiv.org' in self.url:
            self.arxiv = True
    
    def _get_doi_from_original(self):
        result = None

        req = urllib.request.Request(self.url, headers=self.headers)
        with urllib.request.urlopen(req) as page:
            status_code = page.getcode()
            if status_code == 200:
                content = page.read().decode('utf-8')
                soup = bs(content, 'html.parser')
            else:
                return result
        
        for component in soup.find_all(['a', 'p', 'span']):
            text = component.get_text()
            result = extract_doi(text)
            if result is None:
                continue
            else:
                result = result.group(1)
                break
        return result
    
    def _get_doi_from_scihub(self):
        result = None

        url = 'https://sci-hub.se/' + self.url
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req) as page:
            status_code = page.getcode()
            if status_code == 200:
                content = page.read().decode('utf-8')
                soup = bs(content, 'html.parser')
            else:
                return result
        
        for component in soup.find_all(id='link'):
            text = component.a.get_text()
            result = extract_doi(text)
            if result is None:
                continue
            else:
                result = result.group(1)
                break
        return result
    
    def get_doi(self, scihub=True):
        if self.arxiv:
            return None

        if scihub:
            return self._get_doi_from_scihub()
        else:
            return self._get_doi_from_original()

    @staticmethod
    def doi_to_bib(doi):
        url = 'https://dx.doi.org/' + doi
        headers = {'accept': 'application/x-bibtex'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as page:
            status_code = page.getcode()
            if status_code == 200:
                bib = page.read().decode('utf-8')
            else:
                bib = None
        return bib
    
    def get_bib_arxiv(self, indent=2):
        # get publication info using the arxiv API
        arxiv_num = self.url.split('abs/')[-1]
        url = 'https://export.arxiv.org/api/query?id_list=' + arxiv_num
        with urllib.request.urlopen(url) as page:
            status_code = page.getcode()
            if status_code == 200:
                content = page.read().decode('utf-8')
            else:
                return None

        # parse the publication info
        xml = xmltodict.parse(content)['feed']['entry']
        entry = dict()
        entry['title'] = xml['title']
        authors = [author['name'] for author in xml['author']]
        entry['author'] = ' and '.join(authors)
        pub_time = xml['published']
        entry['year'] = str(datetime.fromisoformat(pub_time[:pub_time.find('T')]).year)
        entry['eprint'] = arxiv_num
        entry['archivePrefix'] = 'arXiv'
        entry['primaryClass'] = xml['arxiv:primary_category']['@term']

        bib_id = authors[0].split()[-1].lower()
        bib_id += str(entry['year'])
        bib_id += entry['title'].split()[0].lower()

        # generate bibtex entry
        bib = '@misc{' + bib_id + ',\n'
        for key, value in entry.items():
            bib += ' ' * indent
            bib += key + '={' + value + '}'
            bib += ',\n'
        bib += '}'
        return bib

    def get_bib(self, n_trials=3, indent=2):
        if self.arxiv:
            return self.get_bib_arxiv(indent=indent)

        trial = 0
        while self.doi is None and trial < n_trials:
            if self.doi is None:
                self.doi = self.get_doi(scihub=True)
            if self.doi is None:
                self.doi = self.get_doi(scihub=False)
            trial += 1
        return self.doi_to_bib(self.doi)

def get_bib(url, n_trials=3, indent=2):
    req = SingleRequest(url)
    return req.get_bib(n_trials=n_trials, indent=indent)



class BibParser:
    def __init__(self):
        self.database = None

    def read(self, filename=None, string=None):
        if filename is not None:
            with open(filename, 'r') as file:
                self.database = bp.load(file)
        elif string is not None:
            self.database = bp.loads(string)
        else:
            raise ValueError('Has to specify either filename or string')
    
    def _get_bib_line(self, entry, name, double_quote=False):
        if name not in entry:
            return ''
        
        result = None
        if double_quote:
            if entry[name][0] == '{' and entry[name][-1] == '}':
                result = name + '="' + entry[name] + '"'
            else:
                result = name + '="{' + entry[name] + '}"'
        else:
            result = name + '={' + entry[name] + '}'
        return result

    def _aps_fixes(self, entry):
        if 'publisher' in entry:
            publisher = ''.join([c if c.isalnum() else ' ' for c in entry['publisher']])
            score1 = fuzz.partial_ratio(publisher.lower(), 'american physical society')
            score2 = 100 * ('APS' in publisher)
            if score1 < 60 and score2 < 80:
                return entry
        
        if 'doi' in entry:
            doi = entry['doi']
            if 'physrev' not in doi:
                return entry
        
        """done all sanity checks, start fixes"""

        # somehow bibtex of APS publications from doi.org do not have pages
        # we extract the pages info from the doi
        if 'doi' not in entry:
            return entry
        entry['pages'] = entry['doi'].split('.')[-1]

        return entry
    
    def get_formatted_bib(
        self,
        entry,
        indent=2,
        exclude=None,
        max_authors=100,
    ):
        entry = self._aps_fixes(entry)

        """process title"""
        title_lines = entry['title'].split('\n')
        title_lines = [line.strip() for line in title_lines]
        entry['title'] = ' '.join(title_lines)

        """process author"""
        separator = ' and '
        authors = entry['author'].split(separator)

        # separate initials with space
        for i, author in enumerate(authors):
            authors[i] = ' '.join(_author_initial_spacing_regex.sub(r' \2', author).split())

        # trim after max_authors
        if isinstance(max_authors, int):
            n_authors = len(authors)
            if n_authors <= max_authors:
                pass
            else:
                authors = authors[:max_authors]
                authors.append('others')

        entry['author'] = separator.join(authors)

        """finalize all fields and return"""
        fields = [
            dict(name='title',    double_quote=True),
            dict(name='author',   double_quote=False),
            dict(name='journal',  double_quote=True),
            dict(name='year',     double_quote=False),
            dict(name='volume',   double_quote=False),
            dict(name='number',   double_quote=False),
            dict(name='pages',    double_quote=False),
            dict(name='doi',      double_quote=False),
        ]
        if exclude is not None:
            fields = [field for field in fields]
        bib_lines = ['@' + entry['ENTRYTYPE'] + '{' + entry['ID']]
        for field in fields:
            line = self._get_bib_line(entry, **field)
            if line != '':
                bib_lines.append(line)
        bib = (',\n' + ' ' * indent).join(bib_lines) + ',\n}\n'

        if '_comment' in entry:
            bib = '% ' + entry['_comment'] + '\n' + bib
        return bib
    
    def export_formatted_bibfile(self, path, **kwargs):
        with open(path, 'w') as file:
            for entry in self.database.entries:
                bib = self.get_formatted_bib(entry, **kwargs)
                file.write(bib + '\n')
