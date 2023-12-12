#!/usr/bin/python3

import bs4
import os
import os.path
import random
import re
import requests
import requests.exceptions
import shutil
import sys
import tempfile


url_re = re.compile(r"^(https?:)?//[^/]+\.[a-z]+/.*$", re.IGNORECASE)
schema_re = re.compile("^https?:", re.IGNORECASE)

url_to_scheme = lambda url: url.split(":", 1)[0] + ":"
is_absolute_url = lambda url: schema_re.match(url)
is_scheme_relative_url = lambda strval: strval.startswith("//")

def main():
    file_path = filename_from_args(sys.argv)
    file_name = mktmpd_with_file_and_chdir(file_path)

    with open(file_name) as fh:
        html = "".join(fh.readlines())
        soup = bs4.BeautifulSoup(markup=html, features="lxml")

    title_text = soup.find("title").text.replace("/", "\\")
    assoc_files_dir = title_text + "_files"
    final_html_file = title_text + ".html"
    os.mkdir(assoc_files_dir)

    img_tags = soup.find_all("img", src=True)
    script_tags = soup.find_all("script", src=True)
    link_tags = soup.find_all("link", rel="stylesheet", href=True)
    tags = list(img_tags) + list(script_tags) + list(link_tags)

    # for tag in tags:
    #    url = tag.href if tag.name == "link" else tag.src


def filename_from_args(argv):
    if len(sys.argv) == 1:
        print(
            "Please specify a file to convert to a Web Page, Complete on the commandline."
        )
        exit(1)
    elif len(sys.argv) > 2:
        print("Please specify just one file to convert to a Web Page, Complete.")
        exit(1)
    file_name = sys.argv[1]
    if not os.path.exists(file_name):
        print(f"The file '{file_name}' does not exist.")
        exit(1)
    return os.path.abspath(file_name)


def mktmpd_with_file_and_chdir(old_file_path):
    tempdir = tempfile.mkdtemp()
    os.chdir(tempdir)
    _, file_name = os.path.split(old_file_path)
    new_file_path = os.path.join(tempdir, file_name)
    shutil.copy(old_file_path, new_file_path)
    return file_name


def retrieve_url_into_file(url, file_path):
    file_handle = None
    try:
        bytes_output_count = 0
        file_handle = open(file_path, "wb")
        http_response = requests.get(url, timeout=10)
        if http_response.status_code != 200:
            raise RuntimeError(
                f"Request not successful: got HTTP status code {http_response.status_code}.\n"
            )
        for chunk in http_response.iter_content(chunk_size=1024):
            bytes_output_count += file_handle.write(chunk)
    except OSError as exception:
        raise RuntimeError(
            f"Could not open output file '{file_path}' for writing:\n" + str(exception)
        ) from exception
    except requests.exceptions.SSLError as exception:
        # An error in the SSL handshake, or an expired cert.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to SSL error:\n" + str(exception)
        ) from exception
    except requests.exceptions.TooManyRedirects as exception:
        # The remote host put the client through too many redirects.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to too many redirects:\n"
            + str(exception)
        ) from exception
    except (
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ReadTimeout,
    ) as exception:
        # The connection timed out.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to connection timeout:\n"
            + str(exception)
        ) from exception
    except (requests.exceptions.ConnectionError, IOError) as exception:
        # There was a generic connection error.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to connection error:\n"
            + str(exception)
        ) from exception
    finally:
        if file_handle is not None:
            file_handle.close()
    return bytes_output_count


def url_to_permuted_filename(url):
    if not url_re.match(url):
        raise RuntimeError(f"string '{url}' does not match the pattern for a url")
    return (
        url.rsplit("/", 1)[1]
        + "_"
        + hex(random.randint(4096, 65535)).removeprefix("0x")
    )


if __name__ == "__main__":
    main()
