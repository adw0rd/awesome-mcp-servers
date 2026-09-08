# git-filter-repo --message-callback body; also used for the initial history cleanup.
import re
cleaned = re.sub(br"(?im)^[ \t]*(?:Co-Authored-By|Claude-Session)[ \t]*:[^\r\n]*(?:\r?\n|$)", b"", message)
return cleaned.rstrip(b"\r\n") + b"\n" if cleaned != message else message
