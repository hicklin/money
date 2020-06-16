import os
import re
import json
import copy
import logging
import datetime
import argparse
import subprocess


class Record:
    def __init__(self):
        self.date = None
        self.number = 1
        self.payment_type = ""
        self.entity = ""
        self.entity_location = ""
        self.painIn = 0
        self.painOut = 0
        self.balance = 0

    def clear(self):
        self.date = None
        self.number = 1
        self.payment_type = ""
        self.entity = ""
        self.entity_location = ""
        self.painIn = 0
        self.painOut = 0
        self.balance = 0

    def empty(self):
        """
        :return: True if empty, False otherwise.
        """
        if self.date is None and self.number == 1 and self.payment_type == "" and self.entity == "" and self.entity_location == "" and self.painIn == 0 and self.painOut == 0 and self.balance == 0:
            return True
        else:
            return False

    def json(self):
        return {
            "date": self.date,
            "number": self.number,
            "payment_type": self.payment_type,
            "entity": self.entity,
            "entity_location": self.entity_location,
            "painIn": self.painIn,
            "painOut": self.painOut,
            "balance": self.balance
        }


class StatementProcessor:
    # Constants
    START_DATE_INDEX = 0
    END_DATE_INDEX = 10
    START_PAYMENT_TYPE_INDEX = 15
    END_PAYMENT_TYPE_INDEX = 19
    START_DETAILS_INDEX = 22
    END_DETAILS_INDEX = 54
    START_PAID_OUT_INDEX = 57
    END_PAID_OUT_INDEX = 69
    START_PAID_IN_INDEX = 81
    END_PAID_IN_INDEX = 94
    START_BALANCE_INDEX = 97
#    END_BALANCE_INDEX = :

    def __init__(self):
        self.records = []
        self.current_record = Record()

    @staticmethod
    def convert_pdf_statements(pdf_directory, output_dir):
        pdfs = os.listdir(pdf_directory)
        for pdf in pdfs:
            if os.path.splitext(pdf)[1] == ".pdf":
                pdf_path = os.path.join(pdf_directory, pdf)
                txt_name = os.path.join(output_dir, os.path.basename(pdf).strip(".pdf") + ".txt")
                subprocess.call(["pdftotext", "-layout", pdf_path, txt_name])

    @staticmethod
    def __is_table_start(bits):
        try:
            if bits[1] == "BALANCE BROUGHT FORWARD":
                return True
        except IndexError:
            pass
        return False

    @staticmethod
    def __is_table_end(bits):
        if bits[1] == "BALANCE CARRIED FORWARD":
            return True
        return False

    @staticmethod
    def __get_day(bits):
        try:
            return datetime.datetime.strptime(bits[0], "%d %b %y")
        except ValueError:
            return None

    def __save_current_record(self):
        if not self.current_record.empty():
            logging.debug("Storing record: %s" % self.current_record.json())
            self.records.append(copy.deepcopy(self.current_record))
            self.current_record.clear()

    def __parse_table_line(self, line):
        logging.debug("Parsing line: %s" % line)
        line_len = len(line)
        return_obj = {"date": line[self.START_DATE_INDEX:self.END_DATE_INDEX].strip(" "),
                      "paymentType": line[self.START_PAYMENT_TYPE_INDEX:self.END_PAYMENT_TYPE_INDEX].strip(" "),
                      "details": "",
                      "paidIn": "",
                      "paidOut": "",
                      "balance": ""
                      }

        if line_len >= self.END_DETAILS_INDEX:
            return_obj["details"] = line[self.START_DETAILS_INDEX:self.END_DETAILS_INDEX].strip(" ")
        elif line_len > self.START_DETAILS_INDEX:
            return_obj["details"] = line[self.START_DETAILS_INDEX:].strip(" ")

        if line_len >= self.END_PAID_IN_INDEX:
            return_obj["paidIn"] = line[self.START_PAID_IN_INDEX:self.END_PAID_IN_INDEX].strip(" ")
        elif line_len > self.START_PAID_IN_INDEX:
            return_obj["paidIn"] = line[self.START_PAID_IN_INDEX:].strip(" ")

        if line_len >= self.END_PAID_OUT_INDEX:
            return_obj["paidOut"] = line[self.START_PAID_OUT_INDEX:self.END_PAID_OUT_INDEX].strip(" ")
        elif line_len > self.START_PAID_OUT_INDEX:
            return_obj["paidOut"] = line[self.START_PAID_OUT_INDEX:].strip(" ")

        if line_len > self.START_BALANCE_INDEX:
            return_obj["balance"] = line[self.START_BALANCE_INDEX:].strip(" ")

        # logging.debug("Extracted: %s" % return_obj)
        return return_obj

    def parse_txt_file(self, txt_file):
        f = open(txt_file, "r")
        lines = f.readlines()

        # states
        in_table = False
        current_date = None
        num_of_transaction_in_day = 0

        for line in lines:
            line = line.strip("\n")
            bits = re.split("  +", line)

            if in_table:
                if self.__is_table_end(bits):
                    self.__save_current_record()
                    in_table = False
                    continue
            else:
                in_table = self.__is_table_start(bits)
                continue

            # We are in the table
            line_obj = self.__parse_table_line(line)
            # logging.debug("Got line object: %s" % line_obj)
            if line_obj["date"]:
                # We have started a new day
                current_date = datetime.datetime.strptime(line_obj["date"], "%d %b %y")
                logging.debug("New date: %s" % current_date)

            if line_obj["date"] or line_obj["paymentType"]:  # todo check
                # We have started a new record
                self.__save_current_record()
                self.current_record.date = current_date
                self.current_record.payment_type = line_obj["paymentType"]
                self.current_record.entity = line_obj["details"]
                # logging.debug("Started record: %s" % self.current_record.json())
            else:
                self.current_record.entity_location = line_obj["details"]
                if line_obj["paidOut"]:
                    logging.debug("Found paidOut: %s" % line_obj["paidOut"])
                    self.current_record.painOut = float(line_obj["paidOut"].replace(",", ""))
                if line_obj["paidIn"]:
                    logging.debug("Found paidIn: %s" % line_obj["paidIn"])
                    self.current_record.painIn = float(line_obj["paidIn"].replace(",", ""))
                if line_obj["balance"]:
                    logging.debug("Found balance: %s" % line_obj["balance"])
                    self.current_record.balance = float(line_obj["balance"].replace(",", ""))
                # logging.debug("Finalising record: %s" % self.current_record.json())

    def parse_txt_files(self, txt_directory):
        files = os.listdir(txt_directory)
        for f in files:
            if os.path.split(f)[1] == ".txt":
                self.parse_txt_file(f)

    def export_json(self, output_file):
        output = []
        for record in self.records:
            r = {
                "date": record.date.strftime("%Y-%m-%d"),
                "number": record.number,
                "payment_type": record.payment_type,
                "entity": record.entity,
                "entity_location": record.entity_location,
                "painIn": record.painIn,
                "painOut": record.painOut,
                "balance": record.balance
            }
            output.append(r)

        with open(output_file, 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)

    def export_csv(self, output_file):
        output = "date,number,payment_type,entity,entity_location,painIn,painOut,balance\n"

        for record in self.records:
            # todo check for None printing
            output += "%s,%i,%s,%s,%s,%.2f,%.2f,%.2f\n" % (record.date.strftime("%Y/%m/%d"), record.number,
                                                           record.payment_type, record.entity, record.entity_location,
                                                           record.painIn, record.painOut, record.balance)

        with open(output_file, 'w') as f:
            f.write(output)


if __name__ == '__main__':
    # manage arguments
    parser = argparse.ArgumentParser(description='CAT Connection Journey WiFi Manager')

    parser.add_argument('--debug', default="INFO", choices={"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"},
                        help="Set the debug level. Standard python levels - ERROR, WARNING, INFO, DEBUG")

    args = parser.parse_args()

    logging.basicConfig(level=args.debug, format='%(asctime)s - %(module)s:%(levelname)s: %(message)s')

    pdf_dir = "test"
    txt_out_dir = "test_out"

    logging.info('Starting parsing statements in %s' % pdf_dir)

    processor = StatementProcessor()

    # processor.convert_pdf_statements(pdf_dir, txt_out_dir)
    processor.parse_txt_file("test_out/statements.txt")
    processor.export_json("a.json")
    processor.export_csv("a.csv")

