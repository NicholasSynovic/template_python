from collections import defaultdict
from os import makedirs
from pathlib import Path
from string import Template
from typing import List

import click
from bs4 import BeautifulSoup, Tag
from pandas import DataFrame, Series
from playwright.sync_api import Browser, Page, sync_playwright
from progress.bar import Bar
from requests import Response, get

EPISODE_NUM: int = 1
URL_TEMPLATE: Template = Template(
    template="https://www.miruro.tv/watch?id=${_id}&ep=${episode_num}"
)


def getEpisodeCount(page: Page) -> int:
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
            videoElement: Tag = soup.find(name="video")

            data["video"].append(
                videoElement.find(name="source").get(key="src").__str__()
            )
            data["subtitle"].append(
                videoElement.find(name="track").get(key="src").__str__()
            )

            url: str = URL_TEMPLATE.substitute(_id=_id, episode_num=eid + 1)

            page.goto(url=url, timeout=6000)
            page.wait_for_selector(
                selector="video",
                timeout=6000,
                state="visible",
            )
            page.wait_for_selector(
                selector="source",
                timeout=6000,
                state="attached",
            )
            page.wait_for_selector(
                selector="track",
                timeout=6000,
                state="attached",
            )

            bar.next()

    return data


def downloadFiles(
    urls: Series,
    barName: str,
    outputDir: Path,
    _id: int,
    extension: str = "m3u8",
) -> None:
    counter: int = 1

    url: str
    with Bar(f"Downloading {barName} urls...", max=urls.size) as bar:
        for url in urls:
            outputPath: Path = Path(
                outputDir,
                f"{_id}_{counter}.{extension}",
            )

            resp: Response = get(url=url, timeout=60)

            with open(file=outputPath, mode="w") as fp:
                fp.write(resp.text)

            counter += 1

            bar.next()


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
        page.goto(url=url, timeout=6000)
        page.wait_for_selector(
            selector="video",
            timeout=6000,
            state="visible",
        )
        page.wait_for_selector(
            selector="source",
            timeout=6000,
            state="attached",
        )
        page.wait_for_selector(
            selector="track",
            timeout=6000,
            state="attached",
        )

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
