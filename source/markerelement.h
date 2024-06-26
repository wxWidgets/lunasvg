#ifndef MARKERELEMENT_H
#define MARKERELEMENT_H

#include "graphicselement.h"

namespace wxlunasvg {

class LayoutMarker;

class MarkerElement final : public StyledElement {
public:
    MarkerElement();

    Length refX() const;
    Length refY() const;
    Length markerWidth() const;
    Length markerHeight() const;
    Angle orient() const;
    MarkerUnits markerUnits() const;

    Rect viewBox() const;
    PreserveAspectRatio preserveAspectRatio() const;
    std::unique_ptr<LayoutMarker> getMarker(LayoutContext* context);
};

} // namespace wxlunasvg

#endif // MARKERELEMENT_H
