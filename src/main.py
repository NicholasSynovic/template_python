from collections import defaultdict
from os import makedirs
from pathlib import Path
from string import Template
from typing import List, Tuple

import click
import m3u8
from bs4 import BeautifulSoup, Tag
from m3u8 import M3U8, Playlist
from pandas import DataFrame, Series
from playwright.sync_api import Browser, Page, sync_playwright
from progress.bar import Bar
from requests import Response, get

EPISODE_NUM: int = 1
TIMEOUT_MS: int = 60000
URL_TEMPLATE: Template = Template(
    template="https://www.miruro.tv/watch?id=${_id}&ep=${episode_num}"
)


def updatePage(page: Page, url: str) -> None:
    page.goto(url=url, timeout=TIMEOUT_MS)

    page.wait_for_selector(
        selector="video",
        timeout=TIMEOUT_MS,
        state="visible",
    )

    page.wait_for_selector(
        selector="source",
        timeout=TIMEOUT_MS,
        state="attached",
    )

    page.wait_for_selector(
        selector="track",
        timeout=TIMEOUT_MS,
        state="attached",
    )


def identifySrc(name: str, videoTag: Tag) -> str:
    return videoTag.find(name=name).get(key="src").__str__()


def getEpisodeCount(page: Page) -> int:
    """
    Get the total number of episodes of a particular show ID
    """
    soup: BeautifulSoup = BeautifulSoup(markup=page.content(), features="lxml")

    dropdown: Tag = soup.find(
        name="select",
        attrs={"class": "sc-iwcoAb cqwLjz"},
    )

    lastOption: Tag
    *_, lastOption = dropdown.children

    return int(lastOption.text.strip().split(" ")[-1])


def getDownloadLinks(_id: int, page: Page, episodeCount: int) -> dict[
    str,
    List[str],
]:
    """
    For each episode of a show ID, get the URL to the video source playlist
    file and subtitle file
    """
    data: dict[str, List[str]] = defaultdict(list)

    with Bar(
        "Getting video and subtitle download links",
        max=episodeCount,
    ) as bar:
        eid: int
        for eid in range(1, episodeCount + 1):
            soup: BeautifulSoup = BeautifulSoup(
                markup=page.content(),
                features="lxml",
            )
            videoTag: Tag = soup.find(name="video")

            data["video"].append(
                identifySrc(
                    name="source",
                    videoTag=videoTag,
                )
            )

            data["subtitle"].append(
                identifySrc(
                    name="track",
                    videoTag=videoTag,
                )
            )

            url: str = URL_TEMPLATE.substitute(_id=_id, episode_num=eid + 1)
            updatePage(page=page, url=url)

            bar.next()

    return data


def downloadFiles(
    urls: Series,
    barName: str,
    outputDir: Path,
    _id: int,
    extension: str = "m3u8",
) -> None:
    data: List[str] = []
    counter: int = 1

    url: str
    with Bar(f"Downloading {barName} urls...", max=urls.size) as bar:
        for url in urls:
            outputPath: Path = Path(
                outputDir,
                f"{_id}_{counter}.{extension}",
            )

            resp: Response = get(url=url, timeout=60)

            if extension == "vtt":
                with open(file=outputPath, mode="w") as fp:
                    fp.write(resp.text)
                    fp.close()
                bar.next()
                continue

            playlist: M3U8 = m3u8.loads(content=resp.text)

            hqPL: Playlist = playlist.playlists[0]

            pl: Playlist
            for pl in playlist.playlists:
                """
                Iterate through playlists in m3u8 file and identify the highest
                quality playlist
                """
                hqRes: Tuple[int, int] = hqPL.stream_info.resolution

                if pl.stream_info.resolution[0] > hqRes[0]:
                    hqPL = pl

            url = "/".join(url.split(sep="/")[0:-1]) + "/" + hqPL.uri

            data.append(url)

            bar.next()

    with open(file=Path(outputDir, "playlists.txt"), mode="w") as fp:
        fp.writelines(data)


@click.command()
@click.option(
    "-i",
    "--id",
    "_id",
    help="Show ID",
    required=True,
    type=int,
)
def main(_id: int) -> None:
    outputDir: Path = Path(str(_id))
    url: str = URL_TEMPLATE.substitute(_id=_id, episode_num=1)

    makedirs(name=outputDir, exist_ok=False)

    with sync_playwright() as p:
        browser: Browser = p.firefox.launch(headless=True)
        page: Page = browser.new_page()

        updatePage(page=page, url=url)

        totalEpisodes: int = getEpisodeCount(page=page)
        data: dict[str, List[str]] = getDownloadLinks(
            _id=_id, page=page, episodeCount=totalEpisodes
        )

    df: DataFrame = DataFrame(data=data)
    df.to_json(
        path_or_buf=Path(outputDir, f"{_id}.json"),
        index=False,
        indent=4,
    )

    downloadFiles(
        urls=df["video"],
        barName="video",
        outputDir=outputDir,
        _id=_id,
    )

    downloadFiles(
        urls=df["subtitle"],
        barName="subtitle",
        outputDir=outputDir,
        _id=_id,
        extension="vtt",
    )


if __name__ == "__main__":
    main()
