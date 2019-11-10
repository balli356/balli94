import os
import xml.sax
import whoosh.index as index
from whoosh.fields import *
from whoosh.qparser import MultifieldParser
from whoosh import qparser, scoring
from whoosh.query import Or
from tkinter import *
from threshold_algorithm import *
import pygubu

# PER LE FUNCTION DI SCORING
# https://whoosh.readthedocs.io/en/latest/api/scoring.html#whoosh.scoring.FunctionWeighting

publi = ['article', 'inproceedings', 'mastersthesis', 'phdthesis', 'incollection']
terms_publi = ['key', 'title', 'address', 'author', 'year', 'crossref']
terms_venue = ['key', 'title', 'editor', 'publisher', 'year', 'isbn']

tags = ['article', 'inproceedings', 'proceedings', 'mastersthesis', 'phdthesis', 'incollection', 'book']


def onselect(event):
    w = event.widget
    if len(w.curselection()):
        index = int(w.curselection()[0])
        app.listSelection.delete(0, 'end')
        app.listSelection.insert(END, "score : " + str(app.results[index].score))
        if app.results[index]["tag"] in ['book', 'proceedings']:
            app.listSelection.insert(END, "-------VENUE-------")
        else:
            app.listSelection.insert(END, "----PUBLICATION----")
        for item in app.results[index]:
            if app.results[index][item]:
                app.listSelection.insert(END, item + " : " + app.results[index][item])


def on_next(event):
    if app.len_publi and app.len_venue:
        app.results, app.indice_t = threshold_2(app.results, app.publi_results, app.venue_results, app.len_publi,
                                                app.len_venue, app.indice_t)
        app.listNodes.delete(0, 'end')
        for hit in app.results:
            l = len(hit.pub.get("title"))
            if not l:
                if len(hit.venue.get("title")) > 50:
                    app.listNodes.insert(END, hit.venue.get("title")[:50] + "...")
                else:
                    app.listNodes.insert(END, hit.venue.get("title"))
            elif l > 50:
                app.listNodes.insert(END, hit.pub.get("title")[0:50] + "...")
            else:
                app.listNodes.insert(END, hit.pub.get("title"))
    else:
        app.counter += 1
        for hit in app.results[10 * app.counter:10 * (app.counter + 1)]:
            if len(hit.get("title")) > 50:
                app.listNodes.insert(END, hit.get("title")[0:50] + "...")
            else:
                app.listNodes.insert(END, hit.get("title"))


def onselect_for_dict(event):
    w = event.widget
    if len(w.curselection()):
        index = int(w.curselection()[0])
        app.listSelection.delete(0, 'end')
        app.listSelection.insert(END, "score : " + str(app.results[index].score))
        if app.results[index].pub["key"] != "":
            app.listSelection.insert(END, "----PUBLICATION----")
            for item in app.results[index].pub:
                if app.results[index].pub[item]:
                    app.listSelection.insert(END, item + " : " + app.results[index].pub[item])
        if app.results[index].venue.get("key") != "":
            app.listSelection.insert(END, "-------VENUE-------")
            for item in app.results[index].venue:
                if app.results[index].venue[item]:
                    app.listSelection.insert(END, item + " : " + app.results[index].venue[item])


def do_search(event):
    print("Algoritmo di ranking:" + str(app._model.get()))
    og = qparser.OrGroup.factory(0.9)
    if not app.txtEntry.get():
        return False
    query = app.txtEntry.get()
    regex = r'((?:article|incollection|inproceedings|phdthesis|mastersthesis|publication|venue)(?:.(?:(?:author|title|year|publisher)))?:\s?(?:\*{0,1}\w*\*{0,1})?(?:\".+?\")?)'
    queries = re.findall(regex, query)  # Trovo tutte le ricerche con campi specifici e le metto in una lista
    spec_query = len(queries)
    query = re.sub(regex, ' ',
                   query).strip()  # Tolgo le ricerche che ho trovato prima dalla query. Così ora rimangono solo le ricerche per frase e le parole singole
    if len(query) > 0:
        queries = queries + re.findall(r'".+?"',
                                       query)  # Trovo tutte le ricerche per frase, quindi quelle comprese tra " " e le aggiungo alla lista di prima
        query = re.sub(r'".+?"', '',
                       query)  # Tolgo le ricerche per frase dalla query. Ora quindi rimangono solo le singole parole
        query = re.sub(r'\s+', ' ', query).strip()  # Tolgo gli spazi inutili (dovuti alle sostituzioni di prima)
        queries = queries + query.split(
            ' ')  # Splitto la query per spazi così trovo le singole parole e le aggiungo alla lista
    try:
        queries.remove('')
    except Exception:
        pass
    queries_for_publi = list()
    queries_for_venue = list()
    ven_query = " AND (tag:book OR tag:proceedings)"
    tag_query = " AND (tag:article OR tag:incollection OR tag:phdthesis OR tag:mastersthesis OR tag:inproceedings)"
    start_time = datetime.datetime.now()
    for split in queries[:spec_query]:
        split = split.split(':')
        dotted = split[0].split('.')
        tag = dotted[0]
        if len(dotted) > 1:
            field = dotted[1]
        else:
            field = 0
        if tag in publi:
            tag_query = " AND (tag:" + tag + ")"
        else:
            tag_query = " AND (tag:article OR tag:incollection OR tag:phdthesis OR tag:mastersthesis OR tag:inproceedings)"
        q = qparser.QueryParser(field, schema=schema_publi, group=og)
        if tag in (publi + ['publication']) and field in ['author', 'title', 'year']:
            queries_for_publi.append(q.parse(split[1] + tag_query))
        elif tag == 'venue' and field in ['title', 'publisher']:
            queries_for_venue.append(q.parse(split[1] + ven_query))
        elif not field:
            if tag == 'venue':
                qv = MultifieldParser(terms_venue, schema=schema_venue)
                queries_for_venue.append(qv.parse(split[1] + ven_query))
            else:
                qp = MultifieldParser(terms_publi, schema=schema_publi)
                queries_for_publi.append(qp.parse(split[1] + tag_query))
    if queries[spec_query:]:  # Se son rimasti dei termini non specifici
        qv = MultifieldParser(terms_venue, schema=schema_venue)
        qp = MultifieldParser(terms_publi, schema=schema_publi)
        for split in queries[spec_query:]:
            queries_for_venue.append(qv.parse(split + ven_query))
            queries_for_publi.append(qp.parse(split + tag_query))

    app.venue_results = [y for y in app.get_vx_searcher().search(Or([x for x in queries_for_venue]), limit=None)]
    app.publi_results = [y for y in app.get_px_searcher().search(Or([x for x in queries_for_publi]), limit=None)]

    print("SEARCHING: " + str(datetime.datetime.now() - start_time))
    start_time = datetime.datetime.now()
    app.len_publi = len(app.publi_results)
    app.len_venue = len(app.venue_results)
    print("PUBLICATION LEN:" + str(app.len_publi))
    print("VENUE LEN:" + str(app.len_venue))
    if app.venue_results and app.publi_results:
        app.results, app.indice_t = threshold_2(list(), app.publi_results, app.venue_results, app.len_publi,
                                                app.len_venue)
    print("THRESHOLD: " + str(datetime.datetime.now() - start_time))
    app.listNodes.delete(0, 'end')
    app.listSelection.delete(0, 'end')

    if not app.publi_results or not app.venue_results:
        app.counter = 0
        app.results = app.publi_results + app.venue_results
        for hit in app.results[:10]:
            if len(hit.get("title")) > 50:
                app.listNodes.insert(END, hit.get("title")[0:50] + "...")
            else:
                app.listNodes.insert(END, hit.get("title"))

        app.listNodes.bind('<<ListboxSelect>>', onselect)
    else:
        for hit in app.results:
            l = len(hit.pub.get("title"))
            if not l:
                if len(hit.venue.get("title")) > 50:
                    app.listNodes.insert(END, hit.venue.get("title")[:50] + "...")
                else:
                    app.listNodes.insert(END, hit.venue.get("title"))
            elif l > 50:
                app.listNodes.insert(END, hit.pub.get("title")[0:50] + "...")
            else:
                app.listNodes.insert(END, hit.pub.get("title"))
        app.listNodes.bind('<<ListboxSelect>>', onselect_for_dict)

    print("PUTTING ON LIST: " + str(datetime.datetime.now() - start_time))


class Application:
    def __init__(self, master):
        self.builder = builder = pygubu.Builder()
        self.indice_t = 0
        builder.add_from_file('test.ui')

        self.mainwindow = builder.get_object('search_frame', master)

        self.frmRadiobutton = builder.get_object('frameRadiobutton', master)
        self._model = StringVar()
        for x, text, mode in [(0, "BM25F", "BM25F"), (1, "TF_IDF", "TF_IDF"), (2, "PL2", "PL2")]:
            b = Radiobutton(
                self.frmRadiobutton, text=text,
                variable=self._model, value=mode, command=self.get_value)
            b.grid(row=0, column=x)
        self._model.set("BM25F")
        self.model = 0
        self.listSelection = builder.get_object('listSelection', master)
        self.listNodes = builder.get_object('listNodes', master)

        self.txtEntry = builder.get_object('txtEntry', master)

        self.button = builder.get_object('btnSearch', master)
        self.btnNext = builder.get_object('btnNext', master)
        self.button.bind('<Button-1>', do_search)
        self.btnNext.bind('<Button-1>', on_next)

        self.scroll = builder.get_object('scrollbar', master)
        self.scroll_hor = builder.get_object('scrollbar_hor_selection', master)
        self.scroll_ver = builder.get_object('scrollbar_ver_selection', master)

        self.searcher_venue = [vx.searcher(), vx.searcher(weighting=scoring.TF_IDF), vx.searcher(weighting=scoring.PL2)]
        self.searcher_publi = [px.searcher(), px.searcher(weighting=scoring.TF_IDF), px.searcher(weighting=scoring.PL2)]

        self.listNodes['yscrollcommand'] = self.scroll.set
        self.scroll['command'] = self.listNodes.yview

        self.listSelection['yscrollcommand'] = self.scroll_ver.set
        self.scroll_ver['command'] = self.listSelection.yview
        self.listSelection['xscrollcommand'] = self.scroll_hor.set
        self.scroll_hor['command'] = self.listSelection.xview

        builder.connect_callbacks(self)

    def get_vx_searcher(self):
        return self.searcher_venue[self.model]

    def get_px_searcher(self):
        return self.searcher_publi[self.model]

    def get_value(self):
        if self._model.get() == "BM25F":
            self.model = 0
        elif "TF_IDF" == self._model.get():
            self.model = 1
        else:
            self.model = 2


class IndexHandler(xml.sax.ContentHandler):

    def __init__(self):
        self.CurrentData = ""
        self.tag = ""
        self.key = ""
        self.title = ""
        self.author = ""
        self.year = ""
        self.publisher = ""
        self.crossref = ""
        self.editor = ""
        self.address = ""
        self.pages = ""
        self.ee = ""
        self.isbn = ""

    def startDocument(self):
        print("Parsing")

    def endDocument(self):
        print("Parsed")

    def startElement(self, tag, attributes):
        self.CurrentData = tag
        if self.CurrentData in tags:
            self.tag = self.CurrentData
            self.key = attributes['key']
            self.title = ""
            self.author = ""
            self.year = ""
            self.publisher = ""
            self.crossref = ""
            self.editor = ""
            self.address = ""
            self.pages = ""
            self.ee = ""
            self.isbn = ""

    def characters(self, content):
        if self.tag in publi:
            if self.CurrentData == "title" or self.CurrentData == "i" \
                    or self.CurrentData == "tt" or self.CurrentData == "ref" \
                    or self.CurrentData == "sup" or self.CurrentData == "sub":
                self.title = self.title + content
            elif self.CurrentData == "address":
                self.address = self.address + content
            elif self.CurrentData == "pages":
                self.pages = self.pages + content
            elif self.CurrentData == "author":
                self.author = self.author + content + " "
            elif self.CurrentData == "year":
                self.year = self.year + content
            elif self.CurrentData == "ee":
                self.ee = self.ee + content
            elif self.CurrentData == "crossref":
                self.crossref = self.crossref + content
        elif self.tag in ['book', 'proceedings']:
            if self.CurrentData == "title" or self.CurrentData == "i" \
                    or self.CurrentData == "tt" or self.CurrentData == "ref" \
                    or self.CurrentData == "sup" or self.CurrentData == "sub":
                self.title = self.title + content
            elif self.CurrentData == "editor":
                self.editor = self.editor + content
            elif self.CurrentData == "year":
                self.year = self.year + content
            elif self.CurrentData == "ee":
                self.ee = self.ee + content
            elif self.CurrentData == "isbn":
                self.isbn = self.isbn + content
            elif self.CurrentData == "publisher":
                self.publisher = self.publisher + content

    def endElement(self, tag):
        if self.tag == tag:
            if self.tag in ['book', 'proceedings']:
                writer_venue.add_document(
                    tag=self.tag,
                    key=self.key,
                    title=self.title,
                    year=self.year,
                    editor=self.editor,
                    ee=self.ee,
                    isbn=self.isbn,
                    publisher=self.publisher)
            elif self.tag in publi:
                writer_publi.add_document(
                    tag=self.tag,
                    key=self.key,
                    title=self.title,
                    address=self.address,
                    pages=self.pages,
                    author=self.author,
                    year=self.year,
                    ee=self.ee,
                    crossref=self.crossref)
        self.CurrentData = ""


if __name__ == "__main__":

    schema_publi = Schema(
        tag=ID(stored=True),
        key=ID(stored=True),
        title=TEXT(stored=True),
        address=TEXT(stored=False),
        pages=STORED(),
        author=TEXT(stored=True),
        year=TEXT(stored=True),
        ee=STORED(),
        crossref=ID(stored=True),
    )

    schema_venue = Schema(
        tag=ID(stored=True),
        key=ID(stored=True),
        title=TEXT(stored=True),
        publisher=TEXT(stored=True),
        editor=TEXT(stored=True),
        year=TEXT(stored=True),
        isbn=TEXT(stored=False),
        ee=STORED()
    )

    if not os.path.exists("dblp_index_publication"):
        os.mkdir("dblp_index_publication")
    if not os.path.exists("dblp_index_venue"):
        os.mkdir("dblp_index_venue")
    if not index.exists_in("dblp_index_publication") or not index.exists_in("dblp_index_venue"):
        if not index.exists_in("dblp_index_publication"):
            px = index.create_in("dblp_index_publication", schema_publi)
            writer_publi = px.writer()
        else:
            px = index.open_dir("dblp_index_publication")
        if not index.exists_in("dblp_index_venue"):
            vx = index.create_in("dblp_index_venue", schema_venue)
            writer_venue = vx.writer()
        else:
            vx = index.open_dir("dblp_index_venue")
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        Handler = IndexHandler()
        parser.setContentHandler(Handler)
        parser.parse("dblp.xml")
        writer_publi.commit()
        writer_venue.commit()
    else:
        px = index.open_dir("dblp_index_publication")
        vx = index.open_dir("dblp_index_venue")
    window = Tk()
    window.title("Gestione Informazione")
    window.geometry("1000x580")
    app = Application(window)
    try:
        window.mainloop()
    finally:
        [x.close() for x in app.searcher_venue]
        [x.close() for x in app.searcher_publi]