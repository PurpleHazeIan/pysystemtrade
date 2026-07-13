"""
Clean reporting directory as well as echo file directory.
Drop renaming of echo files as it doesn't serve any useful purpose.

"""

from sysdata.data_blob import dataBlob
from syscore.fileutils import (
    delete_old_files_with_extension_in_pathname,
)

from sysproduction.data.directories import get_echo_file_directory


def clean_truncate_echo_files():
    data = dataBlob()
    cleaner = cleanTruncateEchoFiles(data)
    cleaner.clean_echo_files()
    return None


class cleanTruncateEchoFiles:
    def __init__(self, data: dataBlob):
        self.data = data

    def clean_echo_files(self):
        pathname = get_echo_file_directory()

        days_old = 30
        self.data.log.debug(
            "Deleting files more than %s days old in %s" % (days_old, pathname)
        )
        delete_old_files_with_extension_in_pathname(
            pathname, extension=".txt", days_old=days_old
        )
        # Repeat for report files
        production_config = self.data.config
        pathname = production_config.get_element("reporting_directory")
        self.data.log.debug(
            "Deleting files more than %s days old in %s" % (days_old, pathname)
        )
        delete_old_files_with_extension_in_pathname(
            pathname, extension=".*", days_old=days_old
        )


if __name__ == "__main__":
    clean_truncate_echo_files()
