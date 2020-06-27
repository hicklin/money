from subprocess import Popen, PIPE, call
import logging
import argparse
import os
import datetime


def get_new_name(pdf_path):
    temporary_txt_filename = "temp.txt"
    call(["pdftotext", "-layout", pdf_path, temporary_txt_filename])

    # grep "[0-9]\{1,2\} [a-zA-Z][a-zA-Z]* to [0-9]\{1,2\} [a-zA-Z][a-zA-Z]* [0-9]\{4\}" -m 1 -o temporary_txt_filename
    p = Popen(["grep", "[0-9]\{1,2\} [a-zA-Z][a-zA-Z]* to [0-9]\{1,2\} [a-zA-Z][a-zA-Z]* [0-9]\{4\}", "-m 1", "-o",
               temporary_txt_filename], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    date_range = p.stdout.read().decode()

    os.remove(temporary_txt_filename)

    dates = date_range.strip("\n").split(" to ")
    logging.debug("Got dates: %s" % dates)
    end_date = datetime.datetime.strptime(dates[1], "%d %B %Y")
    start_date = datetime.datetime.strptime("%s %i" % (dates[0], end_date.year), "%d %B %Y")

    return "%s_%s.pdf" % (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))


def rename_pdf(pdf_path):
    new_name = get_new_name(pdf_path)
    new_path = os.path.join(os.path.dirname(pdf_path), new_name)
    if pdf_path == new_path:
        logging.info("No need to rename %s" % pdf_path)
    else:
        logging.info("Renaming %s to %s", pdf_path, new_path)
        os.rename(pdf_path, new_path)


def rename_pdfs(pdf_directory):
    pdfs = os.listdir(pdf_directory)
    for pdf in pdfs:
        if os.path.splitext(pdf)[1] == ".pdf":
            pdf_path = os.path.join(pdf_directory, pdf)
            logging.debug("Attempting to rename %s" % pdf_path)
            rename_pdf(pdf_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--debug', default="INFO", choices={"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"},
                        help="Set the debug level. Standard python levels - ERROR, WARNING, INFO, DEBUG")

    parser.add_argument('--pdf_dir', required=True)

    args = parser.parse_args()

    logging.basicConfig(level=args.debug, format='%(asctime)s - %(module)s:%(levelname)s: %(message)s')

    rename_pdfs(args.pdf_dir)
