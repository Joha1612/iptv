import json
import re
import requests
import base64


def _0xe35c(d, e, f):
    g = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
    h_chars = g[:e]
    i_chars = g[:f]

    j = 0
    d_reversed = d[::-1]

    for c_idx, c_val in enumerate(d_reversed):
        if c_val in h_chars:
            j += h_chars.index(c_val) * (e ** c_idx)

    if j == 0:
        return "0"

    k = ""

    while j > 0:
        k = i_chars[j % f] + k
        j = (j - (j % f)) // f

    return k if k else "0"


def deobfuscate(h, n, t, e):
    r = ""
    i = 0
    len_h = len(h)

    delimiter = n[e]
    n_map = {char: str(idx) for idx, char in enumerate(n)}

    while i < len_h:
        s = ""

        while i < len_h and h[i] != delimiter:
            s += h[i]
            i += 1

        i += 1

        if s:
            s_digits = "".join([n_map.get(c, c) for c in s])
            char_code = int(_0xe35c(s_digits, e, 10)) - t
            r += chr(char_code)

    return r


def decode_base64_url(s):
    s = s.replace("-", "+").replace("_", "/")

    while len(s) % 4:
        s += "="

    return base64.b64decode(s).decode("utf-8")


def get_m3u8_url(channel_url, referer):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer
    }

    try:
        response = requests.get(channel_url, headers=headers)
        response.raise_for_status()

        html_content = response.text

        match = re.search(
            r'eval\(function\(h,u,n,t,e,r\)\{.*?\}\((.*?)\)\)',
            html_content,
            re.DOTALL
        )

        if not match:
            return None

        params_str = match.group(1).strip()

        params_match = re.search(
            r'([\'"])((?:(?!\1).)*)\1,\s*\d+,\s*([\'"])((?:(?!\3).)*)\3,\s*(\d+),\s*(\d+)',
            params_str,
            re.DOTALL
        )

        if not params_match:
            return None

        h = params_match.group(2)
        n = params_match.group(4)
        t = int(params_match.group(5))
        e = int(params_match.group(6))

        deobfuscated_code = deobfuscate(h, n, t, e)

        src_match = re.search(r"src:\s*([\w\d]+)", deobfuscated_code)

        if not src_match:
            return None

        src_variable_name = src_match.group(1)

        assignment_match = re.search(
            r"const\s+" + re.escape(src_variable_name) + r"\s*=\s*(.*?);",
            deobfuscated_code
        )

        if not assignment_match:
            return None

        assignment_line = assignment_match.group(1)

        decoder_func_match = re.search(
            r"function\s+([a-zA-Z0-9_]+)\(str\)",
            deobfuscated_code
        )

        if not decoder_func_match:
            return None

        decoder_func_name = decoder_func_match.group(1)

        parts_vars = re.findall(
            re.escape(decoder_func_name) + r"\((\w+)\)",
            assignment_line
        )

        const_declarations = re.findall(
            r"const\s+(\w+)\s+=\s+'([^']+)';",
            deobfuscated_code
        )

        parts_dict = {k: v for k, v in const_declarations}

        url_parts_b64 = [parts_dict[var] for var in parts_vars]

        decoded_parts = [
            decode_base64_url(part)
            for part in url_parts_b64
        ]

        return "".join(decoded_parts)

    except Exception:
        return None


def get_channels(referer):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer
    }

    try:
        response = requests.get(
            "https://api.cdn-live.tv/api/v1/channels/?user=cdnlivetv&plan=free",
            headers=headers
        )

        response.raise_for_status()

        all_channels = response.json().get("channels", [])

        online_channels = [
            ch for ch in all_channels
            if ch.get("status") == "online"
        ]

        sports_keywords = [
            "sport", "sports", "football",
            "cricket", "espn", "wwe",
            "liga", "premier league",
            "sky sports", "bein sports",
            "fox sports", "sony ten"
        ]

        sports = []
        india = []
        bangladesh = []

        for ch in online_channels:

            name = ch.get("name", "").lower()
            country = str(ch.get("country", "")).lower()

            if any(k in name for k in sports_keywords):
                sports.append(ch)

            if "india" in country:
                india.append(ch)

            if "bangladesh" in country:
                bangladesh.append(ch)

        return sports, india, bangladesh

    except Exception as err:
        print("Channel fetch error:", err)
        return [], [], []


def write_playlist(filename, channels, referer):

    with open(filename, "w", encoding="utf-8") as f:

        f.write(
            '#EXTM3U x-tvg-url="https://github.com/epgshare01/share/raw/master/epg_ripper_ALL_SOURCES1.xml.gz"\n'
        )

        for channel in channels:

            name = channel.get("name")
            code = channel.get("code")
            logo = channel.get("image")
            player_page_url = channel.get("url")

            if not player_page_url:
                continue

            print("Processing:", name)

            m3u8_url = get_m3u8_url(
                player_page_url,
                referer
            )

            if m3u8_url:

                f.write(
                    f'#EXTINF:-1 tvg-id="{code}" tvg-name="{name}" tvg-logo="{logo}",{name}\n'
                )

                f.write(
                    f'#EXTVLCOPT:http-referrer={referer}\n'
                )

                f.write(f"{m3u8_url}\n")


# MAIN EXECUTION

referer_url = "https://edge.cdn-live.ru/"

sports_channels, india_channels, bangladesh_channels = get_channels(referer_url)

write_playlist("sports.m3u", sports_channels, referer_url)
write_playlist("india.m3u", india_channels, referer_url)
write_playlist("bangladesh.m3u", bangladesh_channels, referer_url)

print("✅ Playlist successfully created!")
