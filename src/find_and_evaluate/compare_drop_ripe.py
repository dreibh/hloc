#!/usr/bin/env python3
"""
This module compares the database verifying methods with the rtt method
"""

import argparse
import collections
import mmap
import enum

import src.data_processing.util as util


logger = None


@enum.unique
class CompareType(enum.Enum):
    ripe_c_drop_no_match = 'ripe_c_drop_no_match'
    ripe_c_drop_same = 'ripe_c_drop_same'
    ripe_c_drop_wrong = 'ripe_c_drop_wrong'
    ripe_c_drop_near = 'ripe_c_drop_near'

    ripe_no_v_drop_no_match = 'ripe_no_v_drop_no_match'
    ripe_no_v_drop_match = 'ripe_no_v_drop_match'
    ripe_no_v_drop_wrong = 'ripe_no_v_drop_wrong'

    ripe_no_l_drop_no_match = 'ripe_no_l_drop_no_match'
    ripe_no_l_drop_wrong = 'ripe_no_l_drop_wrong'

    ripe_no_data_drop_no_match = 'ripe_no_data_drop_no_match'
    ripe_no_data_drop_match = 'ripe_no_data_drop_match'


def __create_parser_arguments(parser):
    parser.add_argument('drop_filename_proto', type=str,
                        help=r'The path to the files with {} instead of the filenumber'
                             ' in the name so it is possible to format the string')
    parser.add_argument('ripe_filename_proto', type=str,
                        help=r'The path to the files with {} instead of the filenumber'
                             ' in the name so it is possible to format the string')
    parser.add_argument('-f', '--file-count', type=int, default=8,
                        dest='fileCount',
                        help='number of files from preprocessing')
    parser.add_argument('-loc', '--location-file-name', required=True, type=str,
                        dest='locationFile',
                        help='The path to the location file.'
                             ' The output file from the codes_parser')
    parser.add_argument('-v', '--ip-version', type=str, dest='ip_version',
                        default=util.IPV4_IDENTIFIER,
                        choices=[util.IPV4_IDENTIFIER, util.IPV6_IDENTIFIER],
                        help='specify the ipVersion')
    parser.add_argument('-l', '--logging-file', type=str, default='compare_methods.log',
                        dest='log_file',
                        help='Specify a logging file where the log should be saved')


def main():
    """Main Method"""
    parser = argparse.ArgumentParser()
    __create_parser_arguments(parser)
    args = parser.parse_args()

    global logger
    logger = util.setup_logger(args.log_file, 'compare')
    logger.debug('starting')

    stats = collections.defaultdict(int)

    with open(args.locationFile) as locationFile:
        locations = util.json_load(locationFile)

    for index in range(0, args.fileCount):
        classif_domains = collections.defaultdict(list)
        drop_domains = {}
        with open(args.drop_filename_proto.format(index)) as drop_domain_file, \
                mmap.mmap(drop_domain_file.fileno(), 0,
                          access=mmap.ACCESS_READ) as drop_domain_file_mm:
            line = drop_domain_file_mm.readline().decode('utf-8')
            while len(line):
                domain_list = util.json_loads(line)
                for domain in domain_list:
                    drop_domains[domain.ip_for_version(args.ip_version)] = domain
                line = drop_domain_file_mm.readline().decode('utf-8')
        with open(args.ripe_filename_proto.format(index)) as ripe_domain_file, \
                mmap.mmap(ripe_domain_file.fileno(), 0,
                          access=mmap.ACCESS_READ) as ripe_domain_file_mm:
            line = ripe_domain_file_mm.readline().decode('utf-8')
            while len(line):
                domain_dict = util.json_loads(line)
                for ripe_domain in domain_dict[util.DomainType.correct.value]:
                    ripe_ip = ripe_domain.ip_for_version(args.ip_version)
                    if ripe_ip not in drop_domains:
                        classif_domains[CompareType.ripe_c_drop_no_match].append(
                            (None, ripe_domain))
                    else:
                        drop_domain = drop_domains[ripe_ip]
                        classified = False
                        near_match = False
                        for match in drop_domain.all_matches:
                            if match.location_id == ripe_domain.location_id:
                                classif_domains[CompareType.ripe_c_drop_same].append((drop_domain, ripe_domain))
                                classified = True
                                break
                            else:
                                drop_location = locations[str(match.location_id)]
                                ripe_location = locations[str(ripe_domain.location_id)]
                                ripe_matching_rtt = ripe_domain.matching_match.matching_rtt
                                distance = drop_location.gps_distance_equirectangular(ripe_location)
                                if distance < ripe_matching_rtt * 100:
                                    near_match = True

                        if classified:
                            continue
                        if near_match:
                            classif_domains[CompareType.ripe_c_drop_near].append(
                                (drop_domain, ripe_domain))
                        else:
                            classif_domains[CompareType.ripe_c_drop_wrong].append(
                                (drop_domain, ripe_domain))

                for ripe_domain in domain_dict[util.DomainType.no_verification.value]:
                    ripe_ip = ripe_domain.ip_for_version(args.ip_version)
                    if ripe_ip not in drop_domains:
                        classif_domains[CompareType.ripe_no_v_drop_no_match].append(
                            (None, ripe_domain))
                    else:
                        drop_domain = drop_domains[ripe_ip]
                        possible = False
                        possible_location_ids = [match.location_id
                                                 for match in ripe_domain.possible_matches]
                        for match in drop_domain.all_matches:
                            if match.location_id in possible_location_ids:
                                possible = True
                                break

                        if possible:
                            classif_domains[CompareType.ripe_no_v_drop_match].append(
                                (drop_domain, ripe_domain))
                        else:
                            classif_domains[CompareType.ripe_no_v_drop_wrong].append(
                                (drop_domain, ripe_domain))

                for ripe_domain in domain_dict[util.DomainType.no_location.value]:
                    ripe_ip = ripe_domain.ip_for_version(args.ip_version)
                    if ripe_ip not in drop_domains:
                        classif_domains[CompareType.ripe_no_l_drop_no_match].append(
                            (None, ripe_domain))
                    else:
                        drop_domain = drop_domains[ripe_ip]
                        classif_domains[CompareType.ripe_no_l_drop_wrong].append(
                            (drop_domain, ripe_domain))

                for ripe_domain in domain_dict[util.DomainType.not_responding.value]:
                    ripe_ip = ripe_domain.ip_for_version(args.ip_version)
                    if ripe_ip not in drop_domains:
                        classif_domains[CompareType.ripe_no_data_drop_no_match].append(
                            (None, ripe_domain))
                    else:
                        drop_domain = drop_domains[ripe_ip]
                        classif_domains[CompareType.ripe_no_data_drop_match].append(
                            (drop_domain, ripe_domain))

                line = ripe_domain_file_mm.readline().decode('utf-8')
        with open('compared-ripe-drop-{}.out'.format(index), 'w') as output_file:
            for key, domain_list in classif_domains.items():
                logger.info('{} len {}\n'.format(key, len(domain_list)))
                stats[key] += len(domain_list)
                util.json_dump(domain_list, output_file)
                output_file.write('\n')

        classif_domains.clear()

    for key, value in stats.items():
        logger.info('{} len {}'.format(key, value))


if __name__ == '__main__':
    main()
