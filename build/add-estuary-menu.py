#!/usr/bin/env python3
"""Add HomeTV's section to Kodi 21 Estuary without replacing the skin."""

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


HOME_XML = Path("usr/share/kodi/addons/skin.estuary/xml/Home.xml")
MENU_ID = "23000"
LISTS = (
    ("services", 23100, 32000, "DefaultVideo.png", 24),
    ("media", 23200, 32001, "DefaultFolder.png", 12),
    ("games", 23300, 32002, "DefaultAddonGame.png", 8),
)


def parameter(parent, name, value):
    ET.SubElement(parent, "param", name=name, value=str(value))


def widget_panel():
    panel = ET.Element("control", {"type": "group", "id": MENU_ID})
    ET.SubElement(panel, "visible").text = "String.IsEqual(Container(9000).ListItem.Property(id),hometv)"
    delayed = ET.SubElement(panel, "include", content="Visible_Right_Delayed")
    parameter(delayed, "id", "hometv")
    column = ET.SubElement(panel, "control", {"type": "grouplist", "id": "23001"})
    ET.SubElement(column, "include").text = "WidgetGroupListCommon"
    for path, list_id, label, art, limit in LISTS:
        widget = ET.SubElement(column, "include", content="WidgetListSquare")
        parameter(widget, "content_path", f"plugin://plugin.hometv.widgets/{path}/")
        parameter(widget, "widget_header", f"$ADDON[plugin.hometv.widgets {label}]")
        parameter(widget, "widget_target", "videos")
        parameter(widget, "list_id", list_id)
        parameter(widget, "fallback_icon", art)
        parameter(widget, "widget_limit", limit)
        parameter(widget, "browse_mode", "never")
        parameter(widget, "main_label", "$INFO[ListItem.Label]")
        parameter(widget, "sub_label", "$INFO[ListItem.Label2]")
        parameter(widget, "onclick_condition", "true")
        parameter(widget, "onclick_action", "RunPlugin($INFO[ListItem.FileNameAndPath])")
    return panel


def add_menu(image_root):
    path = image_root / HOME_XML
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    document = ET.parse(path, parser=parser)
    home = document.getroot()
    menu = home.find(".//control[@type='fixedlist'][@id='9000']/content")
    panel = home.find(".//control[@type='group'][@id='2000']")
    if menu is None or panel is None or menu.find("./item/property[@name='id'][.='games']") is None:
        raise ValueError("Штатное меню Kodi Estuary не совпадает с ожидаемой версией")

    existing_item = menu.find("./item/property[@name='id'][.='hometv']")
    existing_panel = panel.find(f"./control[@id='{MENU_ID}']")
    if existing_item is not None:
        if existing_panel is None:
            raise ValueError("Раздел HomeTV Pi добавлен в меню Kodi не полностью")
        return
    occupied = {control.get("id") for control in home.iter("control")}
    reserved = {MENU_ID, "23001", *(str(list_id) for _, list_id, *_ in LISTS)}
    if occupied & reserved:
        raise ValueError("Идентификатор HomeTV Pi уже используется в Kodi Estuary")

    item = ET.Element("item")
    ET.SubElement(item, "label").text = "HomeTV Pi"
    ET.SubElement(item, "onclick").text = "RunAddon(script.hometv)"
    ET.SubElement(item, "property", name="menu_id").text = f"$NUMBER[{MENU_ID}]"
    ET.SubElement(item, "thumb").text = "icons/sidemenu/addons.png"
    ET.SubElement(item, "property", name="id").text = "hometv"
    item.tail = menu.text
    menu.insert(0, item)
    widgets = widget_panel()
    widgets.tail = panel[0].tail
    panel.insert(0, widgets)
    document.write(path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description="Добавить раздел HomeTV Pi в Kodi Estuary")
    parser.add_argument("rootfs", type=Path)
    args = parser.parse_args()
    add_menu(args.rootfs)


if __name__ == "__main__":
    main()
