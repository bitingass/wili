"""Depth ordering shared by Wili's non-attack asset exporters."""


def normalize_draw_order(frame):
    elements=frame['elements']
    elements.sort(key=lambda item:item['matrix'][6])
    for index,element in enumerate(elements):
        element['matrix'][6]=10.0*index/len(elements)-5.0
    return frame
