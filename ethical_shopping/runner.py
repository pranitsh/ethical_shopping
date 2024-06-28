"""Online document gathering toolkit

Benchmarks:
    https://github.com/py-pdf/benchmarks
"""


import pypdfium2 as pdfium
import os
import requests
import pathlib
import textract
from urllib.parse import quote_plus
from urllib.parse import urlparse
import urllib
import functions_framework
import json
import shutil
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
import re
from google.cloud import firestore
import subprocess


def fetch_access_token() -> str | None:
    """
    Fetch or hardcode an access token.

    Returns:
        str | None: The fetched access token if successful, None otherwise.
    
    Acknowledgements:
        MIT License

        Copyright (c) 2024 Arun Shankar

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
    
    Example:
        >>> fetch_access_token() != None
        True
    """
    main_key = ""
    
    if main_key != "":
        return main_key

    cmd = ["gcloud", "auth", "print-access-token"]
    try:
        token = subprocess.check_output(cmd).decode('utf-8').strip()
        return token
    except subprocess.CalledProcessError as e:
        print(f"Failed to fetch access token: {e}")
        return None


def find_urls(query, cx, num_results=3):
    """Fetches company links from Google's Custom Search JSON API.

    Args:
        query (str): The company name to search for.
        cx (str): Your Custom Search Engine ID.
        num_results (int, optional): Maximum number of results to return. Defaults to 10.

    Returns:
        list: A list of company links found in the search results.

    Example:
        >>> query = "Levi Strauss and Co."
        >>> cx = ""
        >>> find_urls(query, cx)[0]
        'https://www.levistrauss.com/'
    """
    query = quote_plus(query)
    url = f'https://www.googleapis.com/customsearch/v1?key=&cx=&q={query}&num={num_results}'

    response = requests.get(url)
    data = response.json()

    links = []
    for item in data.get('items', []):
        links.append(item['link'])

    return links


def generalize_url(url: str) -> str:
    """Converts a URL to a generalized link format.

    This function takes a URL as input and returns a generalized link in the format "[domain.com/](https://domain.com/)*".

    Args:
        url (str): The URL to generalize.

    Returns:
        str: The generalized link.

    Raises:
        ValueError: If the input is not a valid URL.

    Examples:
        >>> generalize_url('https://www.levistrauss.com/')
        'levistrauss.com'
        >>> generalize_url("https://www.apple.com/")
        'apple.com'
    """
    parsed_url = urlparse(url)

    if not all([parsed_url.scheme, parsed_url.netloc]):
        raise ValueError("Invalid URL")

    shortened_url = '.'.join(parsed_url.netloc.split('.')[-2:])

    return f"{shortened_url}"


def find_documents(company, query, cx, filetypes=["pdf", "csv", "txt"], num_results=3):
    """
    Performs a custom Search for documents of specific file types on the company website.

    Args:
        company (str): The company name.
        query (str): The search query.
        cx (str): Your Google Custom Search Engine ID.
        filetypes (list, optional): List of file types to search for (e.g., ["pdf", "docx"]). Defaults to ["pdf", "docx", "pptx", "xlsx", "txt"].
        sites (list, optional): List of websites to search within (e.g., ["*.apple.com"]). Defaults to ["*.apple.com"].
        num_results (int, optional): The maximum number of search results to return. Defaults to 10.

    Returns:
        dict: The JSON response from the Google Custom Search API.

    Example:
        >>> query = "Levi Strauss and Co."
        >>> cx = ""
        >>> len(find_documents(query, "Environmental Consumer Report", cx)) == 5
        True
    """
    filetype_query = " OR ".join([f"filetype:{ft}" for ft in filetypes])
    query += f"{company} ({filetype_query})"
    query = quote_plus(query)
    url = f'https://www.googleapis.com/customsearch/v1?key=&cx=&q={query}&num={num_results}'
    response = requests.get(url)
    data = response.json()
    links = []
    for item in data.get('items', []):
        links.append(item['link'])
    return links


def read_pdf(file) -> str:
    """`read_pdf` reads and returns the text of the pdf file

    Args:
        file: accepts path strings, bytes, and byte buffers

    Returns:
        The string output of the pdf

    Example:
        >>> file = "data/random_text.docx"
        >>> print(process_file(file)[:12])
        Random Text
        <BLANKLINE>
    """
    pdf = pdfium.PdfDocument(file)
    text = ""
    for i in range(len(pdf)):
        page = pdf[i]
        textpage = page.get_textpage()
        text += "\n" + textpage.get_text_bounded()
    return text


def process_file(file):
    """`process_file` reads and returns the text of the file

    Args:
        file: accepts path strings, bytes, and byte buffers

    Returns:
        The string output of the pdf

    Example:
        >>> file = "data/random_text.docx"
        >>> print(process_file(file)[:12])
        Random Text
        <BLANKLINE>
    """
    file_name = pathlib.Path(file)
    try:
        if file_name.suffix == ".pdf":
            return read_pdf(file)
        elif file_name.suffix == ".docx" or file_name.suffix == ".csv" or file_name.suffix == ".epub" or file_name.suffix == ".json" or file_name.suffix == ".html" or file_name.suffix == ".odt" or file_name.suffix == ".pptx" or file_name.suffix == ".txt" or file_name.suffix == ".rtf":
            result_str: str = textract.process(file)
            return result_str.decode('utf_8', errors="ignore")
    except:
        pass


def checksize(url):
    """Prevents downloading files that are too large and getting entity too large errors.

    Example:
        >>> checksize('https://www.levistrauss.com/wp-content/uploads/2021/09/LSCo.-2020-Sustainability-Report.pdf')
        54125447

    Attribution:
        https://stackoverflow.com/a/55226667
    """
    try:
        req = urllib.request.Request(url, method='HEAD')
        f = urllib.request.urlopen(req)
        return int(f.headers['Content-Length'])
    except:
        return 100 * 1000 * 1000


def process_file_links(urls, temp_dir="temp"):
    """
    Downloads files from a list of URLs to a temporary directory.

    Args:
        urls (list): List of URLs to download.
        temp_dir (str, optional): Path to a specific temporary directory. If None, a new one is created.

    Returns:
        list: List of file paths where the downloaded files are stored.
    
    Example:
        >>> urls = ['https://levistrauss.com/wp-content/uploads/2022/09/2021-Sustainability-Report-Summary-.pdf']
        >>> links, summaries, pageses = process_file_links(urls)
        >>> links[0]
        'https://levistrauss.com/wp-content/uploads/2022/09/2021-Sustainability-Report-Summary-.pdf'
        >>> len(summaries[0]) > 0
        True
        >>> len(pageses[0]) > 0
        True
    """
    links = []
    pageses = []
    summaries = []
    path = os.path.abspath('temp')
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs('temp', exist_ok=True)
    size_sum = 0
    for url in urls:
        try:
            # toeing the water
            if size_sum >= 3 * 1000 * 1000:
                break
            add_size = checksize(url)
            if add_size >= 7 * 1000 * 1000:
                continue
            if size_sum + add_size >= 10 * 1000 * 1000:
                size_sum += 100 * 1000
                continue
            else:
                size_sum += add_size
            links.append(url)
            response = requests.get(url)
            # response.raise_for_status()  # Raise an exception for HTTP errors
            filename = os.path.basename(url)  # Extract filename from URL
            filepath = os.path.join(path, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            pages, summary = pdf_answerer("What are the key impacts of this company?", filepath, 'main-403719')
            pageses.append(pages)
            summaries.append(summary)
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {url}: {e}")
    shutil.rmtree(path, ignore_errors=True)
    return links, summaries, pageses


def firebase_cache(company: str, links: list[str] = None, summaries: list[str] = None, pages: list[list[str]] = None):
    """Provides for accessing and updating a Firebase Firestore based on parameters provided.

    Example:
        >>> links, documents = firebase_cache('Levi Strauss and Co.')
        >>> len(links) > 0
        True
        >>> len(documents) > 0
        True
    """
    db = firestore.Client()

    if links == None:
        links = []
        documents = []
        collection_ref = db.collection(company)
        docs = collection_ref.stream()
        for doc in docs:
            links.append(doc.id)
            documents.append(doc.to_dict())
        return links, documents
    else:
        documents = []
        for idx, link in enumerate(links):
            doc_ref = db.collection(company).document(link)
            document = {"summary": summaries[idx], 'pages': pages[idx]}
            doc_ref.set(document)
            documents.append(document)
        return links, documents


def numbers_split(s):
    """
    Splits the input string on any character that is not a number,
    and returns a list of integers that were found in the string.

    Examples:
    >>> numbers_split('1, 2, 3, 4')
    [0, 1, 2, 3]
    >>> numbers_split('a1b2c3')
    [0, 1, 2]
    >>> numbers_split('no numbers here')
    []
    >>> numbers_split('abc123def456')
    [122, 455]
    >>> numbers_split('10.5 and 11.0')
    [9, 4, 10]
    """
    parts = re.split(r'\D+', s)
    parts = [int(part) for part in parts if part.isdigit()]
    parts = [num-1 for num in parts if num != 0]
    return parts


def split_pdf(input_pdf_path, output_pdf_path, page_numbers):
    """
    Splits a PDF and creates a new PDF composed of specified pages from the original PDF.

    Args:
        input_pdf_path (str): Path to the input PDF file.
        output_pdf_path (str): Path to save the output PDF file.
        page_numbers (list of int): List of page numbers to extract (0-based index).

    Examples:
    >>> split_pdf('data/random_text.pdf', 'temp/random_text-new.pdf', [1, 2])
    """
    pdf = pdfium.PdfDocument(input_pdf_path)
    len_pdf = len(pdf)
    page_numbers = [page for page in page_numbers if 0 <= page < len_pdf]

    new_pdf = pdfium.PdfDocument.new()
    os.makedirs('temp', exist_ok=True)
    
    new_pdf.import_pages(pdf, page_numbers, 0)
    new_pdf.save(output_pdf_path)
    return page_numbers


def add_suffix_to_filepath(filepath, suffix="-new"):
    """
    Adds a suffix to the file name before the file extension.

    Args:
        filepath (str): The original file path.
        suffix (str): The suffix to add to the file name.

    Returns:
        str: The new file path with the suffix added.

    Examples:
    >>> add_suffix_to_filepath("test.pdf")
    'temp\\\\test-new.pdf'
    >>> add_suffix_to_filepath("/path/to/test.pdf")
    'temp\\\\test-new.pdf'
    >>> add_suffix_to_filepath("document.txt", "_v2")
    'temp\\\\document_v2.txt'
    """
    directory, filename = os.path.split(filepath)
    name, ext = os.path.splitext(filename)
    new_filename = f"{name}{suffix}{ext}"
    os.makedirs('temp', exist_ok=True)
    return os.path.join('temp', new_filename)


def pdf_answerer(question: str, pdf_location: str, project_id: str) -> list[str]:
    """
    Example:
        >>> project_id = "main-403719"
        >>> pdf_location = "data/random_text.pdf"
        >>> pages, response = pdf_answerer("How many times is random text repeated?", pdf_location, project_id)
        >>> len(pages) > 0
        True
        >>> len(response) > 0
        True
    """
    vertexai.init(project=project_id, location="us-central1")

    file_bytes = pathlib.Path(pdf_location).read_bytes()

    pdf_file = Part.from_data(file_bytes, mime_type="application/pdf")

    generative_multimodal_model = GenerativeModel("gemini-1.5-flash-001")
    page_response = generative_multimodal_model.generate_content([
        pdf_file, 
        "What pages from the pdf answers the below question?",
        question, 
        "Do not use hyphens to indicate ranges. Use only commas to separate pages (i.e ', ')."
        " Again, do not use ranges to indicate pages. Write 0 if there is none."
    ])

    pages = numbers_split(page_response.text)
    if len(pages) > 0:
        path = add_suffix_to_filepath(pdf_location)
        pages = split_pdf(pdf_location, path, pages)

        new_file_bytes = pathlib.Path(path).read_bytes()

        new_pdf_file = Part.from_data(new_file_bytes, mime_type="application/pdf")

        generative_multimodal_model = GenerativeModel("gemini-1.5-flash-001")
        response = generative_multimodal_model.generate_content([
            new_pdf_file, 
            question,
            "Answer within 100 words or less."
        ])

        return pages, response.text
    else:
        return [], ''


@functions_framework.http
def runner(request):
    """HTTP Cloud Function.

    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>

    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    
    Example:
        >>> from flask import Flask, request
        >>> app = Flask(__name__)
        >>> with app.test_request_context(json={'company': 'Levi Strauss and Co.'}):
        ...     response = runner(request)
        >>> print(type(response))
        <class 'str'>
    """
    request_json = request.get_json(silent=True)
    request_args = request.args
    company = ''
    if request_json and 'company' in request_json:
        company = request_json['company']
    elif request_args and 'company' in request_args:
        company = request_args['company']
    if company != '':
        cx = "="
        links, documents = firebase_cache(company)
        if len(links) != 0:
            documents = [document['summary'] for document in documents]
        else:
            links = find_documents(company, "Environmental Report", cx=cx, num_results=3)
            links, summaries, pageses = process_file_links(links)
            firebase_cache(company, links, summaries, pageses)
            documents = summaries
        return json.dumps({'result': '\n\n'.join(documents)})
    return json.dumps({'result': None})


if __name__ == "__main__":
    import doctest
    doctest.testmod()
