import os
import re
import json
import copy
import shutil
import logging
import datetime
import argparse
import subprocess
import numpy as np


class Record:
    def __init__(self):
        self.date = None
        self.number = 1
        self.payment_type = ""
        self.entity = ""
        self.entity_location = ""
        self.paidIn = np.nan
        self.paidOut = np.nan
        self.balance = np.nan

    def clear(self):
        self.date = None
        self.number = 1
        self.payment_type = ""
        self.entity = ""
        self.entity_location = ""
        self.paidIn = np.nan
        self.paidOut = np.nan
        self.balance = np.nan

    def empty(self):
        """
        :return: True if empty, False otherwise.
        """
        if self.date is None and self.number == 1 and self.payment_type == "" and self.entity == "" and self.entity_location == "" and np.isnan(self.paidIn) and np.isnan(self.paidOut) and np.isnan(self.balance):
            return True
        else:
            return False

    def json(self):
        ret = {
            "date": self.date.strftime("%Y-%m-%d %H"),
            "number": self.number,
            "payment_type": self.payment_type,
            "entity": self.entity,
            "entity_location": self.entity_location
        }
        if not np.isnan(self.paidIn):
            ret["paidIn"] = self.paidIn
        if not np.isnan(self.paidOut):
            ret["paidOut"] = self.paidOut
        if not np.isnan(self.balance):
            ret["balance"] = self.balance

        return ret


class StatementProcessor:
    DATE_TEXT = "date"
    PAYMENT_TYPE_AND_DETAILS_TEXT = "payment type and details"
    PAID_OUT_TEXT = "paid out"
    PAID_IN_TEXT = "paid in"
    BALANCE_TEXT = "balance"

    def __init__(self):
        self.records = []
        self.current_record = Record()
        # Constants
        self.start_date_index = 0
        self.end_date_index = 10
        self.start_payment_type_index = 15
        self.end_payment_type_index = 19
        self.start_details_index = 22
        self.end_details_index = 54
        self.start_paid_out_index = 57
        self.end_paid_out_index = 69
        self.start_paid_in_index = 81
        self.end_paid_in_index = 94
        self.start_balance_index = 97

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
            if self.current_record.date is None:
                logging.warning("Logging a record with None date: %s" % self.current_record.json())
            self.records.append(copy.deepcopy(self.current_record))
            self.current_record.clear()

    @staticmethod
    def __line_parse_check(line: str, parsed_obj: dict):
        num_line_chars = len(line.replace(" ", ""))
        num_obj_chars = 0
        for _, value in parsed_obj.items():
            num_obj_chars += len(value.replace(" ", ""))

        if num_line_chars != num_obj_chars:
            logging.warning("Possible incorrect parsing of line\n\tline:  %s\n\tparse: %s" % (line, parsed_obj))
            return False

        return True

    def __parse_table_line(self, line):
        logging.debug("Parsing line: %s" % line)
        line_len = len(line)
        return_obj = {"date": line[self.start_date_index:self.end_date_index].strip(" "),
                      "paymentType": line[self.start_payment_type_index:self.end_payment_type_index].strip(" "),
                      "details": "",
                      "paidIn": "",
                      "paidOut": "",
                      "balance": ""
                      }

        if line_len >= self.end_details_index:
            return_obj["details"] = line[self.start_details_index:self.end_details_index].strip(" ")
        elif line_len > self.start_details_index:
            return_obj["details"] = line[self.start_details_index:].strip(" ")

        if line_len >= self.end_paid_in_index:
            return_obj["paidIn"] = line[self.start_paid_in_index:self.end_paid_in_index].strip(" ")
        elif line_len > self.start_paid_in_index:
            return_obj["paidIn"] = line[self.start_paid_in_index:].strip(" ")

        if line_len >= self.end_paid_out_index:
            return_obj["paidOut"] = line[self.start_paid_out_index:self.end_paid_out_index].strip(" ")
        elif line_len > self.start_paid_out_index:
            return_obj["paidOut"] = line[self.start_paid_out_index:].strip(" ")

        if line_len > self.start_balance_index:
            return_obj["balance"] = line[self.start_balance_index:].strip(" ")

        logging.debug("Parsed as: [%s] [%s] [%s] [%s] [%s] [%s]" % (return_obj["date"], return_obj["paymentType"],
                                                                    return_obj["details"], return_obj["paidOut"],
                                                                    return_obj["paidIn"], return_obj["balance"]))

        _ = self.__line_parse_check(line, return_obj)
        return return_obj

    def parse_txt_file(self, txt_file):
        f = open(txt_file, "r")
        lines = f.readlines()

        # states
        in_table = False
        current_date = None
        daily_transaction_num = 0
        daily_transaction_time_step = datetime.timedelta(hours=1)

        for line in lines:
            line = line.strip("\n")
            bits = re.split("  +", line)

            if in_table:
                if self.__is_table_end(bits):
                    self.__save_current_record()
                    in_table = False
                    continue
            elif line.replace(" ", "").lower() == "datepaymenttypeanddetailspaidoutpaidinbalance":
                logging.debug("Found header: %s" % line)
                self.reset_indices(line)
                continue
            else:
                in_table = self.__is_table_start(bits)
                continue

            # We are in the table
            line_obj = self.__parse_table_line(line)
            logging.debug("Got line object: %s" % line_obj)
            if line_obj["date"]:
                # We have started a new day
                daily_transaction_num = 0
                current_date = datetime.datetime.strptime(line_obj["date"], "%d %b %y")
                logging.debug("New date: %s" % current_date)

            if line_obj["date"] or line_obj["paymentType"]:
                # We have started a new record
                daily_transaction_num += 1
                self.__save_current_record()
                self.current_record.date = current_date + daily_transaction_time_step*daily_transaction_num
                self.current_record.number = daily_transaction_num
                self.current_record.payment_type = line_obj["paymentType"]
                self.current_record.entity = line_obj["details"]
                # logging.debug("Started record: %s" % self.current_record.json())
            else:
                self.current_record.entity_location = line_obj["details"]

            if line_obj["paidOut"]:
                logging.debug("Found paidOut: %s" % line_obj["paidOut"])
                self.current_record.paidOut = float(line_obj["paidOut"].replace(",", ""))
            if line_obj["paidIn"]:
                logging.debug("Found paidIn: %s" % line_obj["paidIn"])
                self.current_record.paidIn = float(line_obj["paidIn"].replace(",", ""))
            if line_obj["balance"]:
                logging.debug("Found balance: %s" % line_obj["balance"])
                self.current_record.balance = float(line_obj["balance"].replace(",", ""))
            # logging.debug("Finalising record: %s" % self.current_record.json())

    def parse_txt_files(self, txt_directory):
        files = os.listdir(txt_directory)
        files.sort()
        for f in files:
            if os.path.splitext(f)[1] == ".txt":
                logging.info("Parsing file: %s" % f)
                self.parse_txt_file(os.path.join(txt_directory, f))

    def export_json(self, output_file):
        output = []
        for record in self.records:
            output.append(record.json())

        with open(output_file, 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)

    def export_csv(self, output_file):
        output = "date\tnumber\tpayment_type\tentity\tentity_location\tpaidIn\tpaidOut\tbalance\n"

        for record in self.records:
            # todo check for None printing
            separator = "\t"
            output_list = ["%s" % record.date.strftime("%Y-%m-%dT%H"),
                           "%i" % record.number,
                           "%s" % record.payment_type,
                           "%s" % record.entity,
                           "%s" % record.entity_location,
                           "%.2f" % record.paidIn,
                           "%.2f" % record.paidOut,
                           "%.2f" % record.balance]
            output += "%s\n" % separator.join(output_list)

        with open(output_file, 'w') as f:
            f.write(output)

    @staticmethod
    def get_start_end_index(search_string, search_for, space_tolerance=2):
        """
        Looks for the start and end indices of the first occurance of a string in a string.
        :param search_string: The string in which the search is to be made
        :param search_for: The string to search for.
        :param space_tolerance: The number of space allowed to be present between letters of the search_for string.
        :return: The start and end indices
        """
        in_string = False
        start_index = 0
        j = 0
        space_count = 0
    
        for index, char in enumerate(search_string):
            # logging.debug("Cuttent; Index: %i, Char: %s" % (index, char))
            if in_string is False and char == search_for[0]:
                # logging.debug("Found a potential start at %i" % index)
                start_index = index
                in_string = True
                j = 1
                continue
    
            if in_string is True:
                if j+1 == len(search_for) and char == search_for[j]:
                    # logging.debug("Found end at %i" % index)
                    return start_index, index
    
                if char == search_for[j]:
                    space_count = 0
                    j += 1
                    continue
                elif char == " ":
                    space_count += 1
                    if space_count > space_tolerance:
                        # logging.debug("Found more than %i spaces in the middle of the string. Resetting." % space_tolerance)
                        in_string = False
                        j = 0
                        start_index = 0
                        continue
                else:
                    # logging.debug("Found something other than the next char or a space. Resetting.")
                    in_string = False
                    j = 0
                    start_index = 0
                    continue
    
        return None, None

    def reset_indices(self, header_string):
        header_string = header_string.lower()

        self.start_date_index, _ = self.get_start_end_index(header_string, self.DATE_TEXT)
        self.end_date_index = self.start_date_index + 14

        ps, pe = self.get_start_end_index(header_string, self.PAYMENT_TYPE_AND_DETAILS_TEXT)
        self.start_payment_type_index = ps - 2
        self.end_payment_type_index = self.start_payment_type_index + 6
        self.start_details_index = ps + 4
        self.end_details_index = pe + 4
        
        ps, pe = self.get_start_end_index(header_string, self.PAID_OUT_TEXT)
        self.start_paid_out_index = ps - 1
        self.end_paid_out_index = pe + 3
        
        ps, pe = self.get_start_end_index(header_string, self.PAID_IN_TEXT)
        self.start_paid_in_index = ps - 1
        self.end_paid_in_index = pe + 3

        ps, pe = self.get_start_end_index(header_string, self.BALANCE_TEXT)
        self.start_balance_index = ps - 3
        
        logging.debug("Reset indices to %i, %i, %i, %i, %i, %i, %i, %i, %i, %i, %i" % (self.start_date_index, 
                                                                                       self.end_date_index, 
                                                                                       self.start_payment_type_index, 
                                                                                       self.end_payment_type_index, 
                                                                                       self.start_details_index, 
                                                                                       self.end_details_index, 
                                                                                       self.start_paid_out_index, 
                                                                                       self.end_paid_out_index, 
                                                                                       self.start_paid_in_index, 
                                                                                       self.end_paid_in_index, 
                                                                                       self.start_balance_index))
        

if __name__ == '__main__':
    temp_txt_out_dir = "temp_out"
    os.makedirs(temp_txt_out_dir, exist_ok=True)

    parser = argparse.ArgumentParser()

    parser.add_argument('--debug', default="INFO", choices={"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"},
                        help="Set the debug level. Standard python levels - ERROR, WARNING, INFO, DEBUG")
    parser.add_argument('-k', '--keep_txt', action="store_true", help="Keep the intermediate text files.")
    parser.add_argument('-d', '--pdf_dir', required=True, help="The directory containing the PDF statements to parse.")
    parser.add_argument('-o', '--output', required=True, help="Name of output JSON and CSV files.")
    args = parser.parse_args()

    logging.basicConfig(level=args.debug, format='%(asctime)s - %(module)s:%(levelname)s: %(message)s')

    processor = StatementProcessor()

    logging.info('Parsing statements in %s' % args.pdf_dir)
    processor.convert_pdf_statements(args.pdf_dir, temp_txt_out_dir)

    processor.parse_txt_files(temp_txt_out_dir)

    logging.info("Exporting data to %s.json and %s.csv" % (args.output, args.output))
    processor.export_json("%s.json" % args.output)
    processor.export_csv("%s.csv" % args.output)

    if not args.keep_txt:
        shutil.rmtree(temp_txt_out_dir, ignore_errors=True)
