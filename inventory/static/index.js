const TABLE_ORDER_NONE = 0;
const TABLE_ORDER_ASC = 1;
const TABLE_ORDER_DESC = -1;


// comparision function with nulls always moved to last
function sortWithNull(a, b, order) {
    // order as usual if both values not null, use order
    if (a != null && b != null) {
        if (a > b) {
            return order;
        } else if (a < b) {
            return order * -1;
        } else {
            return 0;
        }
        // put non-null values as lower than nulls so nulls are put last regardless of order
    } else if (a != null) {
        return -1;
    } else if (b != null) {
        return 1;
    } else {
        return 0;
    }
}


function createAbbreviation(short, long) {
    const abbr = document.createElement("abbr");
    abbr.textContent = short;
    abbr.title = long;
    return abbr;
}


class OrderedTable {
    constructor(id, index, order) {
        this.table = id instanceof HTMLElement ? id : document.getElementById(id);
        if (!this.table || this.table.tagName.toLowerCase() !== "table") {
            throw new Error("not a valid table element");
        }
        const heads = this.table.getElementsByTagName("thead");
        const bodies = this.table.getElementsByTagName("tbody");
        // one thead and one tbody expected, to make things simpler
        if (heads.length !== 1 || bodies.length !== 1) {
            throw new Error("table is expected to have one thead element and one tbody element");
        }
        this.head = heads[0];
        this.body = bodies[0];

        // verify there is one header row
        const headerRows = this.head.getElementsByTagName("tr");
        if (headerRows.length !== 1) {
            throw new Error("table header is expected to have a single row");
        }

        this.header = headerRows[0];
        this.rows = Array.from(this.body.getElementsByTagName("tr"));

        // verify all cells do not span multiple rows or columns
        const hasSpan = e => e.hasAttribute("rowspan")
            || e.hasAttribute("colspan")
            || Array.from(e.children).some(hasSpan);
        if (hasSpan(this.header) || this.rows.some(hasSpan)) {
            throw new Error(
                "table is expected to have no cells spanning multiple rows or columns"
            );
        }

        this.columns = Array.from(this.header.children).map((c, i) => {
            const lowerName = (c.dataset.columnName || c.textContent).toLowerCase()
            const type = (c.dataset.columnType || "string").toLowerCase();
            if (!["string", "int", "float", "date"].includes(type)) {
                throw new Error(`column type '${type}' not recognised`);
            }
            return {
                index: i,
                element: c,
                name: c.textContent,
                lowerName: lowerName,
                type: type,
                reverse: !!c.dataset.columnReverse,
                order: TABLE_ORDER_NONE
            };
        });

        // Set onclick event for each header cell
        for (const [i, c] of this.columns.entries()) {
            c.element.onclick = () => this._sort(i, null);
            c.element.style.cursor = "pointer";
            c.element.title = `order table by ${c.lowerName} ascending`;
        }

        // set order at start if arguments defined
        if (index != null && index >= 0 && index < this.columns.length) {
            const start = (!order || order >= 0) ? TABLE_ORDER_ASC : TABLE_ORDER_DESC;
            this._sort(index, start);
        }
    }

    _sort(index, order) {
        const column = this.columns[index];
        // set header names with arrows indicating which column is sorted
        let newOrder;
        // look at existing order being used or override with argument
        if (order && order >= 0 || !order && column.order <= 0) {
            newOrder = TABLE_ORDER_ASC;
        } else {
            newOrder = TABLE_ORDER_DESC;
        }
        this._setColumns(column, newOrder);
        this._sortRows(column);
    }

    _setColumns(column, newOrder) {
        for (const [i, c] of this.columns.entries()) {
            // reset header content before appending arrow if needed
            c.element.textContent = c.name;
            if (i === column.index && newOrder < 0) {
                c.order = TABLE_ORDER_DESC;
                c.element.append(" ", createAbbreviation("↓", "descending"));
                c.element.title = `order table by ${c.lowerName} descending`;
            } else if (i === column.index && newOrder > 0) {
                c.order = TABLE_ORDER_ASC;
                c.element.append(" ", createAbbreviation("↑", "ascending"));
                c.element.title = `order table by ${c.lowerName} descending`;
            } else if (c.order !== TABLE_ORDER_NONE) {
                c.order = TABLE_ORDER_NONE;
                c.element.title = `order table by ${c.lowerName} ascending`;
            }
        }
    }

    _sortRows(column) {
        // find list of corresponding values to sort by
        const values = this._columnValues(column);
        const reverse = (column.reverse) ? -1 : 1;
        // indices should match so sort list of rows by values
        const copy = [...this.rows];
        this.rows.sort((a, b) => {
            const i = copy.indexOf(a);
            const j = copy.indexOf(b);
            return sortWithNull(values[i], values[j], column.order * reverse);
        });
        // apply new order to dom
        for (const r of this.rows) {
            this.body.appendChild(r);
        }
    }

    _columnValues(column) {
        return this.rows.map(r => {
            const cell = r.children.item(column.index);
            if (!cell) {
                return null;
            }
            const value = (typeof cell.dataset.columnKey !== "undefined")
                ? cell.dataset.columnKey : cell.textContent;
            let result;
            switch (column.type) {
                case "int":
                    result = parseInt(value);
                    return (isNaN(result)) ? null : result;
                case "float":
                    result = parseFloat(value);
                    return (isNaN(result)) ? null : result;
                case "date":
                    result = parseInt(value);
                    return (isNaN(result)) ? null : new Date(result);
                default:
                    // string is the default type here
                    // make string ordering case insensitive; treat empty strings as null
                    return (value) ? value.toUpperCase() : null;
            }
        });
    }
}


const DAY = 1000 * 60 * 60 * 24;
const WEEK = DAY * 7;
const NEUTRAL = "#ddd";


function getUniqueId(name) {
    let count = 0;
    let id = name;
    while (document.getElementById(id)) {
        count++;
        id = name + '-' + count;
    }
    return id;
}


function roundDecimal(number, places) {
    const dp = places || 0;
    if (dp) {
        return number.toFixed(dp).replace(/0+$/, "").replace(/\.$/, "");
    } else {
        return Math.round(number)
    }
}


// chart based on:
// https://observablehq.com/@d3/line-chart
// https://observablehq.com/@d3/multi-line-chart
// https://observablehq.com/@d3/zoomable-area-chart
// https://observablehq.com/@d3/focus-context

class InventoryChart {
    constructor(container, data, height, width) {
        this.container = (container instanceof HTMLElement)
            ? container : document.getElementById(container);
        this.font = window.getComputedStyle(this.container).fontFamily;

        this.chartHeight = height || 400;
        this.focusHeight = this.chartHeight / 4;
        this.width = width || 600;
        this.margin = {top: 20, right: 20, bottom: 30, left: 30};
        this.colours = d3.schemeTableau10.map(d3.color);

        this._collectData(data);
        if (!this.items) {
            return;
        }
        this._setUpAxes();
        this._setUpChart();
        this._setUpFocus();
        this._setUpHover();
    }

    _colour(index) {
        return this.colours[index % this.colours.length];
    }

    _collectData(data) {
        // filter out all items with less than two data points
        const filtered = data.filter(i => i.records.length >= 2);
        if (!filtered.length) {
            return;
        }

        this.items = filtered.map(i => i.name);
        this.averages = filtered.map(g => parseFloat(g.avg) || null);
        // collect all existing data points
        this.existing = filtered.map(g => {
            return g.records.map(r => ({date: Date.parse(r.a), value: parseFloat(r.q)}))
        });
        this.dates = d3.extent(this.existing.flatMap(g => g.map(r => r.date)));
        this.latest = this.dates[1];
        // set end of data to now or 1 week ahead of the latest record, whichever is earlier
        const dateEnd = this.dates[1] = d3.max([new Date(), this.dates[1] + WEEK]);
        // pad the vertical axis
        this.values = [0, d3.max(this.existing.flatMap(g => g.map(r => r.value))) * 1.05];

        // project predicted inventory as straight line based on average daily use
        this.projected = this.existing.map((group, i) => {
            // average per millisecond
            const average = this.averages[i] / DAY;
            // latest date and value for this item
            const last = group[group.length - 1];
            let predicted;
            if (average) {
                // find new date when inventory is predicted to hit zero
                const newDate = last.date + last.value / average;
                if (newDate <= dateEnd) {
                    // end date is before 1 week, so go ahead
                    predicted = {date: newDate, value: 0};
                } else {
                    // find value at 1 week ahead and use that
                    const endValue = last.value - average * (dateEnd - last.date);
                    predicted =  {date: dateEnd, value: endValue};
                }
            } else {
                predicted = {date: dateEnd, value: last.value};
            }
            return [last, predicted];
        });
    }

    _setUpAxes() {
        // base scales for x and y axes
        this.xScale = d3.scaleUtc()
            .domain(this.dates)
            .range([this.margin.left, this.width - this.margin.right]);
        this.yScale = d3.scaleLinear()
            .domain(this.values)
            .range([this.chartHeight - this.margin.bottom, this.margin.top])
            .nice();
        // x-axis scaling with zoom
        this.xZoom = this.xScale;

        // definitions for x and y axes; height argument for setting axis on multiple charts
        this.xAxis = (g, x, height) => g
            .attr("transform", `translate(0, ${height - this.margin.bottom})`)
            .call(d3.axisBottom(x).ticks(this.width / 80).tickSizeOuter(0));
        this.yAxis = (g, y) => g
            .attr("transform", `translate(${this.margin.left}, 0)`)
            .call(d3.axisLeft(y).ticks(2))
            .call(g => g.select(".domain").remove());

        // function for path generation using scales
        this.line = (data, xs, ys) => d3.line()
            .defined(d => !isNaN(d.value))
            .x(d => (xs || this.xScale)(d.date))
            .y(d => (ys || this.yScale)(d.value))(data);
    }

    _setUpChart() {
        // base svg container, append to container
        this.chart = d3.create("svg").attr("viewBox", [0, 0, this.width, this.chartHeight]);
        this.container.appendChild(this.chart.node());

        // clip path to contain all paths within axes
        this.clipId = getUniqueId("clip");
        this.chart.append("clipPath")
            .attr("id", this.clipId)
            .append("rect")
            .attr("x", this.margin.left)
            .attr("y", this.margin.top)
            .attr("width", this.width - this.margin.left - this.margin.right)
            .attr("height", this.chartHeight - this.margin.top - this.margin.bottom);

        // append axes to chart
        this.chartX = this.chart
            .append("g")
            .call(this.xAxis, this.xScale, this.chartHeight)
            .attr("font-family", this.font);
        this.chartY = this.chart
            .append("g")
            .call(this.yAxis, this.yScale)
            .attr("font-family", this.font);

        // append lines to chart
        this.chartPastLines = this._addPastLines(this.chart);
        this.chartFutureLines = this._addFutureLines(this.chart);
    }

    _setUpFocus() {
        // default 4 days behind, 3 days ahead
        this.defaultSelection = [
            this.xScale(d3.max([this.dates[0], d3.utcDay.offset(this.latest, -4)])),
            this.xScale(d3.min([this.dates[1], d3.utcDay.offset(this.latest, 3)])),
        ];

        this.focus = d3.create("svg").attr("viewBox", [0, 0, this.width, this.focusHeight]);
        this.container.appendChild(this.focus.node());

        this.brush = d3.brushX()
            .extent([
                [this.margin.left, 0.5],
                [this.width - this.margin.right, this.focusHeight - this.margin.bottom + 0.5]
            ])
            .on("brush", this._brushed)
            .on("end", this._brushEnd);

        // smaller height to set axis correctly
        this.focus
            .append("g")
            .call(this.xAxis, this.xScale, this.focusHeight)
            .attr("font-family", this.font);

        // smaller scale for brush chart
        const scaledY = this.yScale
            .copy()
            .range([this.focusHeight - this.margin.bottom, this.margin.top]);
        this._addPastLines(this.focus, null, scaledY);
        this._addFutureLines(this.focus, null, scaledY);

        this.gb = this.focus
            .append("g")
            .call(this.brush)
            .call(this.brush.move, this.defaultSelection);
    }

    _brushed = () => {
        if (d3.event.selection) {
            // set scale and range corresponding to brush
            this.xZoom = this.xScale.copy().domain(d3.event.selection.map(this.xScale.invert));
            this.chartX.call(this.xAxis, this.xZoom, this.chartHeight);
            this.chartPastLines
                .data(this.existing)
                .call(p => p.attr("d", l => this.line(l, this.xZoom)));
            this.chartFutureLines
                .data(this.projected)
                .call(p => p.attr("d", l => this.line(l, this.xZoom)));
        }
    }

    _brushEnd = () => {
        if (!d3.event.selection) {
            // reset brush in case brush input fails
            this.gb.call(this.brush.move, this.defaultSelection);
        }
    }

    _addPastLines(svg, xs, ys) {
        return svg
            .append("g")
            .attr("fill", "none")
            .attr("stroke-width", 1.5)
            .attr("stroke-linejoin", "round")
            .selectAll("path")
            .data(this.existing)
            .join("path")
            .style("mix-blend-mode", "multiply")
            .attr("clip-path", "url(#" + this.clipId + ")")
            .attr("stroke", (_, i) => this._colour(i))
            .attr("d", l => this.line(l, xs, ys));
    }

    _addFutureLines(svg, xs, ys) {
        return svg
            .append("g")
            .attr("fill", "none")
            .attr("stroke-width", 1.5)
            .attr("stroke-linejoin", "round")
            .attr("stroke-dasharray", "4 2")
            .selectAll("path")
            .data(this.projected)
            .join("path")
            .style("mix-blend-mode", "multiply")
            .attr("clip-path", "url(#" + this.clipId + ")")
            .attr("stroke", (_, i) => this._colour(i))
            .attr("d", l => this.line(l, xs, ys));
    }

    _setUpHover() {
        this.hoverDot = this.chart.append("g").attr("display", "none");
        this.hoverDot.append("circle").attr("r", 2.5);
        this.hoverDot.append("text")
            .attr("font-size", 10)
            .attr("y", -8);

        // apply font style after rendering
        this.hoverDot.select("text").attr("font-family", this.font);

        if ("ontouchstart" in document) {
            this.chart
                .style("-webkit-tap-highlight-color", "transparent")
                .on("touchmove", this._moveTouch)
                .on("touchstart", this._enter)
                .on("touchend", this._leave);
        } else {
            this.chart
                .on("mousemove", this._moveMouse)
                .on("mouseenter", this._enter)
                .on("mouseleave", this._leave);
        }
    }

    _moveTouch = () => {
        d3.event.preventDefault();
        const touch = d3.touch(this.chart.node());
        if (touch != null) {
            const [x, y] = touch;
            this._move(x, y);
        }
    }

    _moveMouse = () => {
        d3.event.preventDefault();
        const mouse = d3.mouse(this.chart.node());
        const [x, y] = mouse;
        this._move(x, y);
    }

    _move = (x, y) => {
        // find the nearest set of coordinates
        let distance, item, closest;
        let min = Infinity;
        for (const i of this.existing.keys()) {
            for (const point of this.existing[i]) {
                distance = this._squaredDistance(x, y, point);
                if (distance < min) {
                    item = i;
                    closest = point;
                    min = distance;
                }
            }
            // only need last point on projected line
            distance = this._squaredDistance(x, y, this.projected[i][1]);
            if (distance < min) {
                item = i;
                closest = this.projected[i][1];
                min = distance;
            }
        }
        if (item == null) {
            return;
        }

        const closestX = this.xZoom(closest.date);
        const closestY = this.yScale(closest.value);
        // Set text anchor for dot based on position relative to svg canvas
        const textAnchor = (closestX < this.width / 3)
            ? "start" : (closestX >= this.width * 2 / 3) ? "end" : "middle";

        this.hoverDot.attr("transform", `translate(${closestX},${closestY})`);
        this.hoverDot
            .select("text")
            .attr("text-anchor", textAnchor)
            .text(`${this.items[item]}: ${roundDecimal(closest.value, 3)}`);

        if (this.items.length > 1) {
            this.chartPastLines
                .attr("stroke", (_, i) => (i === item) ? this._colour(i) : NEUTRAL)
                .filter((_, i) => i === item)
                .raise();
            this.chartFutureLines
                .attr("stroke", (_, i) => (i === item) ? this._colour(i) : NEUTRAL)
                .filter((_, i) => i === item)
                .raise();
        }
    }

    _squaredDistance(x, y, point) {
        return Math.pow(x - this.xZoom(point.date), 2)
            + Math.pow(y - this.yScale(point.value), 2);
    }

    _enter = () => {
        this.hoverDot.attr("display", null);
        if (this.items.length > 1) {
            this.chartPastLines.style("mix-blend-mode", null).attr("stroke", () => NEUTRAL);
            this.chartFutureLines.style("mix-blend-mode", null).attr("stroke", () => NEUTRAL);
        }
    }

    _leave = () => {
        this.hoverDot.attr("display", "none");
        if (this.items.length > 1) {
            this.chartPastLines
                .style("mix-blend-mode", "multiply")
                .attr("stroke", (_, i) => this._colour(i));
            this.chartFutureLines
                .style("mix-blend-mode", "multiply")
                .attr("stroke", (_, i) => this._colour(i));
        }
    }
}
