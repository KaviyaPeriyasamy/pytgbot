# -*- coding: utf-8 -*-
import json
import re
from abc import abstractmethod

from datetime import timedelta, datetime
from DictObject import DictObject

from luckydonaldUtils.logger import logging
from luckydonaldUtils.encoding import unicode_type, to_unicode as u, to_native as n
from luckydonaldUtils.exceptions import assert_type_or_raise

from ..exceptions import TgApiServerException, TgApiParseException, TgApiException
from ..exceptions import TgApiTypeError, TgApiResponseException
from ..api_types.sendable.inline import InlineQueryResult
from ..api_types import from_array_list


__author__ = 'luckydonald'
__all__ = ["Bot"]

logger = logging.getLogger(__name__)


class BotBase(object):
    _base_url = "https://api.telegram.org/bot{api_key}/{command}"  # you shouldn't change that.

    def __init__(self, api_key, return_python_objects=True):
        """
        A Bot instance. From here you can call all the functions.
        The api key can be optained from @BotFather, see https://core.telegram.org/bots#6-botfather

        :param api_key: The API key. Something like "ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        :type  api_key: str

        :param return_python_objects: If it should convert the json to `pytgbot.api_types.**` objects. Default: `True`
        :type  return_python_objects: bool
        """
        from datetime import datetime

        if api_key is None or not api_key:
            raise ValueError("No api_key given.")
        self.api_key = api_key
        self.return_python_objects = return_python_objects
        self._last_update = datetime.now()
        self._id = None        # will be filled when using the property .id or .username, or when calling ._load_info()
        self._username = None  # will be filled when using the property .id or .username, or when calling ._load_info()
    # end def __init__

    def send_msg(self, *args, **kwargs):
        """ alias to :func:`send_message` """
        return self.send_message(*args, **kwargs)
    # end def send_msg

    def _prepare_request(self, command, query):
        """
        Prepares the command url, and converts the query json.

        :param command: The Url command parameter
        :type  command: str

        :param query: Will get json encoded.

        :return: params and a url, for use with requests etc.
        """
        from pytgbot.api_types.sendable import Sendable
        from pytgbot.api_types import as_array
        import json

        params = {}
        for key in query.keys():
            element = query[key]
            if element is not None:
                if isinstance(element, Sendable):
                    params[key] = json.dumps(as_array(element))
                else:
                    params[key] = element
        url = self._base_url.format(api_key=n(self.api_key), command=n(command))
        return url, params
    # end def _prepare_request

    def _postprocess_request(self, request, response, json):
        """
        This converts the response to either the response or a parsed :class:`pytgbot.api_types.receivable.Receivable`.

        :param request: the request
        :type request: request.Request|httpx.Request

        :param response: the request response
        :type  response: requests.Response|httpx.Response

        :param json: the parsed json array
        :type  json: dict

        :return: The json response from the server, or, if `self.return_python_objects` is `True`, a parsed return type.
        :rtype:  DictObject.DictObject | pytgbot.api_types.receivable.Receivable
        """
        from DictObject import DictObject

        try:
            logger.debug(json)
            res = DictObject.objectify(json)
        except Exception as e:
            raise TgApiResponseException('Parsing answer as json failed.', response, e)
        # end if
        res["_response"] = response  # TODO: does this failes on json lists? Does TG does that?
        # TG should always return an dict, with at least a status or something.
        if self.return_python_objects:
            if res.ok is not True:
                raise TgApiServerException(
                    error_code=res.error_code if "error_code" in res else None,
                    response=res.response if "response" in res else None,
                    description=res.description if "description" in res else None,
                    request=request
                )
            # end if not ok
            if "result" not in res:
                raise TgApiParseException('Key "result" is missing.')
            # end if no result
            return res.result
        # end if return_python_objects
        return res
    # end def _postprocess_request

    def _prepare_fileupload(self, _command, _file_is_optional, file_param_name, kwargs, value):
        """
        :param file_param_name: For what field the file should be uploaded.
        :type  file_param_name: str

        :param value: File to send. You can either pass a file_id as String to resend a file
                      file that is already on the Telegram servers, or upload a new file,
                      specifying the file path as :class:`pytgbot.api_types.sendable.files.InputFile`.
                      If `_file_is_optional` is set to `True`, it can also be set to `None`.
        :type  value: pytgbot.api_types.sendable.files.InputFile | str | None

        :param _command: Overwrite the command to be send.
                         Default is to convert `file_param_name` to camel case (`"voice_note"` -> `"sendVoiceNote"`)
        :type  _command: str|None

        :param _file_is_optional: If the file (`value`) is allowed to be None.
        :type  _file_is_optional: bool

        :param kwargs: will get json encoded.

        :return: The json response from the server, or, if `self.return_python_objects` is `True`, a parsed return type.
        :rtype: DictObject.DictObject | pytgbot.api_types.receivable.Receivable

        :raises TgApiTypeError, TgApiParseException, TgApiServerException: Everything from :meth:`Bot.do`, and :class:`TgApiTypeError`
        """
        from ..api_types.sendable.files import InputFile
        from luckydonaldUtils.encoding import unicode_type
        from luckydonaldUtils.encoding import to_native as n
        if value is None and _file_is_optional:
            # Is None but set optional, so do nothing.
            pass
        elif isinstance(value, str):
            kwargs[file_param_name] = str(value)
        elif isinstance(value, unicode_type):
            kwargs[file_param_name] = n(value)
        elif isinstance(value, InputFile):
            files = value.get_request_files(file_param_name)
            if "files" in kwargs and kwargs["files"]:
                # already are some files there, merge them.
                assert isinstance(kwargs["files"], dict), \
                    'The files should be of type dict, but are of type {}.'.format(type(kwargs["files"]))
                for key in files.keys():
                    assert key not in kwargs["files"], '{key} would be overwritten!'
                    kwargs["files"][key] = files[key]
                # end for
            else:
                # no files so far
                kwargs["files"] = files
            # end if
        else:
            raise TgApiTypeError(
                "Parameter {key} is not type (str, {text_type}, {input_file_type}), but type {type}".format(
                    key=file_param_name, type=type(value), input_file_type=InputFile, text_type=unicode_type))
        # end if
        if not _command:
            # command as camelCase  # "voice_note" -> "sendVoiceNote"  # https://stackoverflow.com/a/10984923/3423324
            command = re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), "send_" + file_param_name)
        else:
            command = _command
        # end def
        return command
    # end def _prepare_fileupload

    def get_download_url(self, file):
        """
        Creates a url to download the file.

        Note: Contains the secret API key, so you should not share this url!

        :param file: The File you want to get the url to download.
        :type  file: pytgbot.api_types.receivable.media.File

        :return: url
        :rtype: str
        """
        from ..api_types.receivable.media import File
        assert isinstance(file, File)
        return file.get_download_url(self.api_key)
    # end def get_download_url

    @abstractmethod
    def get_updates(self, offset=None, limit=100, poll_timeout=0, allowed_updates=None, request_timeout=None, delta=timedelta(milliseconds=100), error_as_empty=False):
        raise NotImplementedError('subclass needs to overwrite this.')
    # end def

    @abstractmethod
    def do(self, command, files=None, use_long_polling=False, request_timeout=None, **query):
        raise NotImplementedError('subclass needs to overwrite this.')
    # end def

    @abstractmethod
    def get_me(self):
        raise NotImplementedError('subclass needs to overwrite this.')
    # end def

    @abstractmethod
    def _load_info(self):
        raise NotImplementedError('subclass needs to overwrite this.')
    # end def
# end class Bot
