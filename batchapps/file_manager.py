#-------------------------------------------------------------------------
# The Azure Batch Apps Python Client
#
# Copyright (c) Microsoft Corporation. All rights reserved. 
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#--------------------------------------------------------------------------

from .files import UserFile, FileCollection
from .config import Configuration
from .api import BatchAppsApi

import logging
import glob
import os

class FileManager(object):
    """
    This is the only class that a user should need to import to access all
    user data and asset files manipulation.
    Contains only general functionality for the creation of :class:`.UserFile`
    and :class:`.FileCollection` objects.
    """

    def __init__(self, credentials, cfg=None):
        """
        :Args:
            - credentials (:class:`.Credentials`): The Users authentication.

        :Kwargs:
            - cfg (:class:`.Configuration`): Logging and application
              configuration. Unless set this is None, in which case a default
              configuration will be used.
        """
        if not cfg:
            cfg = Configuration()
        self._log = logging.getLogger('batch_apps')
        self._client = BatchAppsApi(credentials, cfg)

    def create_file_set(self, *files):
        """Create a file collection to assign to job.

        :Args:
            - files (:class:`.UserFile`, list): *Optional*. Any files to be
              included in the newly created set. This can be passed in a
              individual :class:`.UserFile` objects or as a list of
              :class:`.UserFile` objects.

        :Returns:
            - :class:`.FileCollection` The new FileCollection, containing any
              specified userfiles.

        :Raises:
            - :exc:`.FileInvalidException` Raised by the FileCollection class
              if ``files`` contains non-:class:`.UserFile` objects.
        """
        self._log.info("Creating new FileCollection with included "
                       "userfiles: {0}".format(len(files)))

        file_list = []
        for _file in files:

            if isinstance(_file, list):
                file_list.extend(_file)

            else:
                file_list.append(_file)

        return FileCollection(self._client, *list(set(file_list)))

    def create_file(self, fullpath):
        """
        .. warning:: Deprecated. Use :meth:`.file_from_path()`.

        Create a userfile object.

        :Args:
            - fullpath (str): Full path to the file

        :Returns:
            - :class:`.UserFile`: The file object reference for the
              supplied file path. This will be returned regardless of
              whether the file actually exists.
        """
        self._log.warning("create_file() has been deprecated. "
                          "Please use file_from_path()")
        return self.file_from_path(fullpath)

    def file_from_path(self, fullpath):
        """
        Create a new userfile object.

        :Args:
            - fullpath (str): Full path to the file

        :Returns:
            - :class:`.UserFile`: The file object reference for the
              supplied file path. This will be returned regardless of
              whether the file actually exists.
        """
        self._log.info("Creating new userfile at path: {0}".format(fullpath))
        return UserFile(self._client, str(fullpath))

    def files_from_dir(self, top_dir, recursive=False, pattern='*'):
        """Create a file set from contents of a directory.

        :Args:
            - top_dir (str): The full path to the directory, the contents
              of which will be added to the set.

        :Kwargs:
            - recursive (bool): Whether the set will include the contents of
              subdirectories. The default is ``False``
            - pattern (str): The pattern to apply to filter director contents.
              Default: ``"*"``, i.e. all files included.

        :Returns:
            - :class:`.FileCollection` The new FileCollection containing an
              :class:`.UserFile` object for each non-filtered file in the
              specified directory.

        :Raises:
            - :class:`NotADirectoryError` if the supplied directory does not
              exist.
        """
        top_dir = str(top_dir)
        if not os.path.isdir(top_dir):
            raise OSError("Supplied directory invalid")

        self._log.info("Creating FileCollection from contents of "
                       "directory: {0}".format(top_dir))

        if not recursive:
            top = os.path.join(top_dir, pattern)
            self._log.debug(
                "Non-recursive search in with pattern: {0}".format(top))

            file_list = [os.path.normpath(a) for a in glob.glob(top)
                         if os.path.isfile(a)]

        else:
            self._log.debug("Recursive search in the following directories...")
            file_list = []
            file_list.extend(
                [os.path.normpath(a)
                 for a in glob.glob(os.path.join(top_dir, pattern))
                 if os.path.isfile(a)])

            for dirs in os.walk(top_dir):

                for folder in dirs[1]:
                    self._log.debug(
                        "Searching in {0}".format(
                            os.path.join(dirs[0], folder)))

                    top = os.path.join(dirs[0], folder, pattern)
                    file_list.extend(
                        [os.path.normpath(a) for a in glob.glob(top)
                         if os.path.isfile(a)])

        self._log.debug(
            "Collected files: {0}".format(
                [os.path.basename(a) for a in file_list]))

        return self.create_file_set(
            [UserFile(self._client, a) for a in file_list])

    def list_files(self):
        """List all the files previously uploaded by the user.

        :Returns:
            - If successful, A list of :class:`.UserFile` objects,
              else ``None``.
        """
        all_files = self._client.list_files()

        if all_files.success:
            cloud_files = [UserFile(self._client, _file)
                           for _file in all_files.result]

            return cloud_files

        else:
            #self._log.error(all_files.result.msg)
            raise all_files.result

    def find_file(self, name, last_mod, full_path=None):
        """Find the reference to a specific file on the cloud.

        :Args:
            - name (str): The name of the file to be located in the cloud.
            - last_mod (str): The last modified timestamp of the
              file.

        :Kwargs:
            - full_path (str): The full path of the file to be found.
              If omitted, and file path is a match.

        :Returns:
            - A list of :class:`.UserFile` objects that are uploaded and
              match the specified names.
        """
        spec = {'FileName':name, 'Timestamp':last_mod}
        if full_path:
            spec['OriginalPath'] = full_path

        matches = self._client.query_files(spec)
        if matches.success:
            cloud_files = [UserFile(self._client, _file)
                           for _file in matches.result]

            return cloud_files
        else:
            #self._log.error(matches.result.msg)
            raise matches.result

    def find_files(self, name):
        """Returns a list of existing files in the users account meeting
        certain criteria.

        :Args:
            - name (str, list): The filename of file to find, including
              extension. Can also be a list of filenames.

        :Returns:
            - A list of :class:`.UserFile` objects that are uploaded and
              match the specified names.
        """
        matches = self._client.query_files(name)
        if matches.success:
            cloud_files = [UserFile(self._client, _file)
                           for _file in matches.result]

            return cloud_files
        else:
            #self._log.error(matches.result.msg)
            raise matches.result
