from scielo_usage_counter import log_handler

from metrics.services.parsing.metadata import build_url_translation_manager


def setup_parsing_environment(log_file, robots_list, mmdb):
    log_parser = log_handler.LogParser(
        mmdb_data=mmdb.data,
        robots_list=robots_list,
        output_mode="dict",
    )
    log_parser.logfile = log_file.path

    url_translator_manager = build_url_translation_manager(log_file)
    return log_parser, url_translator_manager
