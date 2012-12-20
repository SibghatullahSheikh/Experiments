from urllib import urlencode, urlopen
from collections import defaultdict
from datetime import datetime, date
from xml.etree import ElementTree
from os.path import join, exists
from os import makedirs

from pymongo import MongoClient

from matplotlib import pyplot
from matplotlib.dates import strpdate2num

SORT_FIELD = 'contributors'

NOT_GENERAL_PROGRAMMING = [
    'HTML', 'CSS', 'Haml', 'ClearSilver',
    'XML', 'XSL Transformation', 'XML Schema', 'MXML', 'XAML', 'QML',
    'shell script', 'DOS batch script', 'AWK', 'Vim Script', 'DCL', 'NSIS',
    'Make', 'Automake', 'Autoconf', 'Ebuild', 'CMake', 'Exheres', 'Jam',
    'TeX/LaTeX', 'MetaFont', 'MetaPost',
    'SQL', 'IDL/PV-WAVE/GDL',
    'Assembly', 'OpenGL Shading', 'CUDA',
    'Matlab', 'Octave', 'R', 'Scilab',
    'Stratego', 'Puppet',
    'VHDL',
]
ALIAS = {
    # C++ family
    'C/C++':'C++',
    # Lisp family
    'Emacs Lisp': 'Lisp', 'Scheme': 'Lisp', 'Racket': 'Lisp', 'Clojure': 'Lisp',
    # Fortran Family
    'Fortran (Fixed-format)': 'Fortran', 'Fortran (Free-format)': 'Fortran',
    # Basic Family
    'Visual Basic': 'Basic', 'Structured Basic': 'Basic', 'Classic Basic': 'Basic',
    # Modula Family
    'Modula-2': 'Modula', 'Modula-3': 'Modula', 'Oberon': 'Modula'
}

# Popularity threshold
DB_THRESHOLD   =  0.45 # for being stored in the DB
PLOT_THRESHOLD = 10.00 # for being plotted

from settings import *
from algorithms.clusters.hierarchical import Item, find_clusters

def get_top_languages(key, sort):
    languages = defaultdict(int)
    params = {
        'api_key': key,
        'sort'   : sort,
        'page'   : 1
    }
    while True:
        query = urlencode(sorted(params.items()))
        url = "http://www.ohloh.net/languages.xml?%s" % query

        print 'request:', url
        xml = urlopen(url).read()

        root = ElementTree.fromstring(xml)
        error = root.find("error")
        if error != None:
            raise Exception('Ohloh Error:', ElementTree.tostring(error))

        if root.find("items_returned").text == "0":
            break

        for lang_node in root.findall("result/language"):
            name = lang_node.find('nice_name').text
            if name in NOT_GENERAL_PROGRAMMING:
                continue
            if name in ALIAS:
                name = ALIAS[name]
            value = int(lang_node.find(sort).text)
            languages[name] += value

        params['page'] += 1

    return sorted([(c, l) for l, c in languages.iteritems()], reverse=True)


def get_langpop_db():
    # Language Popularity DB
    connection = MongoClient(MONGO_URL, MONGO_PORT)
    db = connection[MONGO_DB]
    db.authenticate(MONGO_USER, MONGO_PWD)
    return db.langpop


def query_today_data(db):
    # Unique id for the day
    t = datetime.now()
    day_id = t.year*10000+t.month*100+t.day

    # Check if there is already an entry for today
    data = db.find_one({"_id": day_id})
    if data:
        print 'Language popularity data already stored in the DB'
        return

    languages = get_top_languages(OHLOH_KEY, SORT_FIELD)

    # Normalize to the most popular language
    normalized_data = {"_id":day_id}
    unit = 100.0 / float(languages[0][0])

    items = []
    for i, (value, lang) in enumerate(languages):
        n = value * unit
        if n < DB_THRESHOLD: break
        print '%2d) %.2f - %s' % (i+1, n, lang)
        items.append(Item(lang, (n,)))
        normalized_data[lang] = n

    # Find Popularity Clusters
    cluster_names = ('Ubiquitous', 'Very Popular', 'Popular', 'Niche')
    clusters = find_clusters(items, cluster_names)
    clusters.sort(reverse=True)

    print "\nPopularity Clusters:"
    for i, label in enumerate(cluster_names):
        print clusters[i]

    print "\nStore data in DB:"
    item_id = db.insert(normalized_data)
    print item_id


class LanguagePopularity:
    date_parser = strpdate2num("%Y%m%d")

    def __init__(self, name):
        self.name = name
        self.data = {}
        self.matplotlib_dates = []
        self.popularity = []

    def add_record(self, day, popularity):
        self.data[day] = popularity
        self.matplotlib_dates.append(LanguagePopularity.date_parser(day))
        self.popularity.append(popularity)

    def has_been_popular(self, popularity_threshold):
        for p in self.popularity:
            if p >= popularity_threshold:
                return True
        return False

    def __cmp__(self, other):
        return cmp(self.popularity[-1], other.popularity[-1])


class TSV:
    def __init__(self, path):
        self.f = open(path, 'w')

    def add_entry(self, entry):
        self.f.write('\t'.join(entry) + '\n')

    def __del__(self):
        self.f.close()

def plot_data(db):
    langpop = {}
    dates = []
    for data in db.find().sort("_id"):
        day = str(data.pop('_id'))
        dates.append(day)
        for lang, popularity in data.iteritems():
            if lang not in langpop:
                langpop[lang] = LanguagePopularity(lang)
            langpop[lang].add_record(day, popularity)
    languages = langpop.values()
    languages.sort(reverse=True)

    fig = pyplot.figure()
    subplot = fig.add_subplot(111)

    popular_languages = []
    for lang in languages:
        # Plot only languages that has been more popular than a given threshold
        if not lang.has_been_popular(PLOT_THRESHOLD): break
        popular_languages.append(lang)
        subplot.plot_date(lang.matplotlib_dates, lang.popularity, 'o-', label=lang.name)

    pyplot.ylim([0, 110])
    subplot.legend(loc='upper left', fancybox=True)

    print "Saving image"
    fig.autofmt_xdate()

    ohloh_dir = join(WWW_STATIC, 'ohloh')
    if not exists(ohloh_dir):
        makedirs(ohloh_dir)
    fig.savefig(join(ohloh_dir, 'language_popularity.png'))

    print "Generating TSV"
    tsv = TSV(join(ohloh_dir, 'language_popularity.tsv'))

    # title
    tsv.add_entry(["date"] + [lang.name for lang in popular_languages])

    # data
    for day in dates:
        entry = [day]
        for lang in popular_languages:
            entry.append(str(lang.data.get(day, 0)))
        tsv.add_entry(entry)


if __name__ == '__main__':
    db = get_langpop_db()
    query_today_data(db)
    plot_data(db)
