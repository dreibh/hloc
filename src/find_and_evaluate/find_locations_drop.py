#!/usr/bin/env python3

import pickle
import argparse
import collections
import time
import src.data_processing.util as util
import multiprocessing as mp
import pprint
import heapq
from src.data_processing.preprocess_drop_rules import RULE_NAME

logger = None


def __create_parser_arguments(parser):
    """Creates the arguments for the parser"""
    parser.add_argument('doaminfilename_proto', type=str,
                        help='The path to the files with {} instead of the filenumber'
                             ' in the name so it is possible to format the string')
    parser.add_argument('trie_file', type=str,
                        help='The path to the pickle file with the trie from the'
                             'create_trie script')
    parser.add_argument('drop_rules_file', type=str,
                        help='The path to the json file with the drop rules from the'
                             'preprocess_drop_rules script')
    parser.add_argument('-n', '--file-count', type=int, default=8,
                        dest='fileCount',
                        help='number of files from preprocessing')
    parser.add_argument('-a', '--amount-dns-entries', type=int, default=0,
                        dest='amount',
                        help='Specify the amount of dns entries which should be searched'
                             ' per Process. Default is 0 which means all dns entries')
    parser.add_argument('-l', '--logging-file', type=str, default='find_drop.log', dest='log_file',
                        help='Specify a logging file where the log should be saved')
    parser.add_argument('-s', '--statistics-file', type=str, default='drop_statistics.log',
                        dest='statistics_file_path', help='Specify a statistics logging file')
    # parser.add_argument('-r', '--profile', help='Profiles process 1 and 7',
    #                     dest='profile', action='store_true')


def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    __create_parser_arguments(parser)
    args = parser.parse_args()

    global logger
    logger = util.setup_logger(args.log_file, 'find')

    with open(args.trie_file, 'rb') as trie_file:
        trie = pickle.load(trie_file)

    with open(args.drop_rules_file) as drop_rules_file:
        drop_rules = util.json_load(drop_rules_file)

    processes = []
    for index in range(0, args.fileCount):
        process = mp.Process(target=start_search_in_file,
                             args=(args.doaminfilename_proto, index, trie,
                                   drop_rules, args.amount, args.statistics_file_path),
                             name='find_drop_{}'.format(index))
        processes.append(process)

    for process in processes:
        process.start()

    for process in processes:
        process.join()


def start_search_in_file(domainfile_proto: str, index: int, trie, drop_rules: [str, object],
                         amount: int, stats_file_path: str):
    """Start searching in file and timer to know the elapsed time"""
    start_time = time.time()
    search_in_file(domainfile_proto, index, trie, drop_rules, amount, stats_file_path)

    end_time = time.time()
    logger.info('running time: {}'.format((end_time - start_time)))


def search_in_file(domainfile_proto: str, index: int, trie, drop_rules: [str, object],
                   amount: int,  stats_file_path: str):
    """Search in file"""
    match_count = collections.defaultdict(int)
    count_domains = 0
    entries_stats = collections.defaultdict(dict)

    def generate_def_dcts(gen_rules: [str, object]):
        for gen_rule in gen_rules.values():
            if isinstance(gen_rule, dict):
                generate_def_dcts(gen_rule)
                continue
            entries_stats[gen_rule.name] = collections.defaultdict(int)

    generate_def_dcts(drop_rules)

    filename = domainfile_proto.format(index)
    with open(filename) as domain_file, \
            open(util.remove_file_ending(filename) + '.found', 'w') as loc_found_file, \
            open(util.remove_file_ending(filename) + '.notfound', 'w') as no_loc_found_file, \
            open(util.remove_file_ending(filename) + '.found-wo-trie', 'w') as loc_found_wo_file:
        domain_count = collections.defaultdict(int)
        domains_w_location = []
        domains_wo_location = []
        domains_no_location = []

        def save_domain_with_location(loc_domain):
            domains_w_location.append(loc_domain)
            if len(domains_w_location) >= 10**3:
                domain_count['domains_w_location'] += len(domains_w_location)
                util.json_dump(domains_w_location, loc_found_file)
                loc_found_file.write('\n')
                del domains_w_location[:]

        def save_domain_wo_location(loc_domain):
            domains_wo_location.append(loc_domain)
            if len(domains_wo_location) >= 10**3:
                domain_count['domains_wo_location'] += len(domains_wo_location)
                util.json_dump(domains_wo_location, loc_found_wo_file)
                loc_found_wo_file.write('\n')
                del domains_wo_location[:]

        def save_domain_no_location(loc_domain):
            domains_no_location.append(loc_domain)
            if len(domains_no_location) >= 10**3:
                domain_count['domains_no_location'] += len(domains_no_location)
                util.json_dump(domains_no_location, no_loc_found_file)
                no_loc_found_file.write('\n')
                del domains_no_location[:]

        def find_rules_for_domain(domain_obj: util.Domain):
            tmp_dct = drop_rules
            for next_key in domain_obj.drop_domain_keys:
                if next_key not in tmp_dct:
                    break
                if RULE_NAME in tmp_dct[next_key]:
                    yield tmp_dct[next_key][RULE_NAME]
                tmp_dct = tmp_dct[next_key]

        for line in domain_file:
            amount -= 1
            domains = util.json_loads(line)
            for domain in domains:
                count_domains += 1
                matched = False
                locations_present = False
                found_false_positive = False
                rules = find_rules_for_domain(domain)
                for rule in rules:
                    entries_stats[rule.name]['rules_used_count'] += 1
                    for regex, code_type in rule.regex_pattern_rules:
                        match = regex.search(domain.domain_name)
                        if match:
                            if not matched:
                                entries_stats[rule.name]['domains_with_rule_match_count'] += 1
                                matched = True
                            matched_str = match.group('type')
                            locations = [loc for loc in trie.get(matched_str, [])
                                         if loc[1] == code_type.value]
                            if locations and not locations_present:
                                entries_stats[rule.name]['domains_with_location_count'] += 1
                                locations_present = True
                            elif not locations_present:
                                found_false_positive = True
                            entries_stats[rule.name]['total_amount_found_locations'] += \
                                len(locations)
                            for location in locations:
                                match_count[code_type.name] += 1
                                for label in domain.domain_labels:
                                    if matched_str in label.label:
                                        label.matches.append(util.DomainLabelMatch(location[0],
                                                                                   code_type,
                                                                                   matched_str))
                                        break

                if found_false_positive and locations_present:
                    entries_stats[rule.name]['false_positive_with_found_location'] += 1
                if found_false_positive:
                    entries_stats[rule.name]['false_positives'] += 1

                if locations_present:
                    save_domain_with_location(domain)
                elif matched:
                    save_domain_wo_location(domain)
                else:
                    save_domain_no_location(domain)

            if amount == 0:
                break

        util.json_dump(domains_w_location, loc_found_file)
        util.json_dump(domains_wo_location, loc_found_wo_file)
        util.json_dump(domains_no_location, no_loc_found_file)
        domain_count['domains_w_location'] += len(domains_w_location)
        domain_count['domains_wo_location'] += len(domains_wo_location)
        domain_count['domains_no_location'] += len(domains_no_location)

        new_better_stats = {}
        for rule_name, rule_stat in entries_stats.items():
            if not isinstance(rule_stat, dict):
                continue
            new_better_stats[rule_name] = {'count': rule_stat['rules_used_count']}
            if rule_stat['rules_used_count'] < 10:
                new_better_stats[rule_name]['low_usage'] = True
                continue
            new_better_stats[rule_name]['matching_percent'] = \
                rule_stat['domains_with_rule_match_count'] / rule_stat['rules_used_count']
            new_better_stats[rule_name]['true_matching_percent'] = \
                rule_stat['domains_with_location_count'] / rule_stat['rules_used_count']
            if rule_stat['domains_with_rule_match_count'] > 0:
                new_better_stats[rule_name]['matching_percent_related'] = \
                    rule_stat['domains_with_location_count'] / \
                    rule_stat['domains_with_rule_match_count']
            else:
                new_better_stats[rule_name]['matching_percent_related'] = 2

        with open(stats_file_path, 'w') as stats_file:
            util.json_dump(new_better_stats, stats_file)

        stats_for_used_rules = {}
        for rule_name, stats in new_better_stats.items():
            if 'low_usage' not in stats:
                stats_for_used_rules[rule_name] = stats

        ten_most_matching = heapq.nlargest(10, stats_for_used_rules.items(),
                                           key=lambda stat: stat[1]['matching_percent'])
        ten_most_true_matching = heapq.nlargest(10, stats_for_used_rules.items(),
                                                key=lambda stat: stat[1]['true_matching_percent'])
        ten_least_matching = heapq.nsmallest(10, stats_for_used_rules.items(),
                                             key=lambda stat: stat[1]['matching_percent'])
        ten_least_true_matching = heapq.nsmallest(10, stats_for_used_rules.items(),
                                                  key=lambda stat: stat[1]['true_matching_percent'])
        ten_lowest_related_matching = heapq.nsmallest(
            10, stats_for_used_rules.items(), key=lambda stat: stat[1]['matching_percent_related'])

        logger.info('Total amount domains: {}'.format(count_domains))
        logger.info('Total amount domains with location: {}'.format(
            domain_count['domains_w_location']))
        logger.info('Total amount domains without location code: {}'.format(
            domain_count['domains_wo_location']))
        logger.info('Total amount domains without location: {}'.format(
            domain_count['domains_no_location']))
        logger.info('Total amount rules: {}'.format(len(new_better_stats)))
        logger.info('Amount used rules: {}'.format(len(stats_for_used_rules)))
        logger.info('10 rules with highest matching percent: {}'.format(
            pprint.pformat(ten_most_matching, indent=4)))
        logger.info('10 rules with highest true matching percent: {}'.format(
            pprint.pformat(ten_most_true_matching, indent=4)))
        logger.info('10 rules with lowest matching percent: {}'.format(
            pprint.pformat(ten_least_matching, indent=4)))
        logger.info('10 rules with lowest true matching percent: {}'.format(
            pprint.pformat(ten_least_true_matching, indent=4)))
        logger.info('10 rules with lowest related matching percent: {}'.format(
            pprint.pformat(ten_lowest_related_matching, indent=4)))

        logger.info('matching stats {}'.format(pprint.pformat(match_count, indent=4)))

if __name__ == '__main__':
    main()
