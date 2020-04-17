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


// chart based on:
// https://observablehq.com/@d3/line-chart
// https://observablehq.com/@d3/multi-line-chart
// https://observablehq.com/@d3/zoomable-area-chart

// TODO: Initial range covering last and next 7 days?

const DAY = 1000 * 60 * 60 * 24;
const WEEK = DAY * 7;


function getUniqueId(name) {
    let count = 0;
    let id = name;
    while (document.getElementById(id)) {
        count++;
        id = name + '-' + count;
    }
    return id;
}


class InventoryChart {
    constructor(container, data, height, width) {
        this.container = (container instanceof HTMLElement)
            ? container : document.getElementById(container);
        this.font = window.getComputedStyle(this.container).fontFamily;

        this.height = height || 300;
        this.width = width || 600;
        this.margin = {top: 20, right: 20, bottom: 30, left: 30};

        this._collectData(data);
        if (!this.items) {
            return;
        }
        this._setUpAxes();
        this._setUpChart();
        this._setUpZoom();
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
        // pad the vertical axis
        this.values = [0, d3.max(this.existing.flatMap(g => g.map(r => r.value))) * 1.1];

        // set end of data to 1 week ahead of latest data
        const dateEnd = this.dates[1] + WEEK;
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
        // x- and y-axis scaling
        this.xScale = d3.scaleUtc()
            .domain(this.dates)
            .range([this.margin.left, this.width - this.margin.right]);
        this.yScale = d3.scaleLinear()
            .domain(this.values)
            .range([this.height - this.margin.bottom, this.margin.top])
            .nice();
        // x-axis scaling with zoom
        this.xZoom = this.xScale;

        // x- and y-axis definitions
        this.xAxis = (g, x) => g
            .attr("transform", `translate(0, ${this.height - this.margin.bottom})`)
            .call(d3.axisBottom(x).ticks(this.width / 80).tickSizeOuter(0));
        this.yAxis = (g, y) => g
            .attr("transform", `translate(${this.margin.left}, 0)`)
            .call(d3.axisLeft(y).ticks(2))
            .call(g => g.select(".domain").remove());

        // path generation
        this.line = (data, x) => d3.line()
            // .curve(d3.curveStepAfter)
            .defined(d => !isNaN(d.value))
            .x(d => (x || this.xScale)(d.date))
            .y(d => this.yScale(d.value))(data);
    }

    _setUpChart() {
        // base svg container, append to container
        this.svg = d3.create("svg").attr("viewBox", [0, 0, this.width, this.height]);
        this.container.appendChild(this.svg.node());

        // clip path to contain all paths within axes
        this.clipId = getUniqueId("clip");
        this.svg.append("clipPath")
            .attr("id", this.clipId)
            .append("rect")
            .attr("x", this.margin.left)
            .attr("y", this.margin.top)
            .attr("width", this.width - this.margin.left - this.margin.right)
            .attr("height", this.height - this.margin.top - this.margin.bottom);

        // append axes to svg container
        this.gx = this.svg
            .append("g")
            .call(this.xAxis, this.xScale)
            .attr("font-family", this.font);
        this.gy = this.svg
            .append("g")
            .call(this.yAxis, this.yScale)
            .attr("font-family", this.font);

        this.pastLines = this.svg
            .append("g")
            .attr("fill", "none")
            .attr("stroke", "steelblue")
            .attr("stroke-width", 1.5)
            .attr("stroke-linejoin", "round")
            .selectAll("path")
            .data(this.existing)
            .join("path")
            .style("mix-blend-mode", "multiply")
            .attr("clip-path", "url(#" + this.clipId + ")")
            .attr("d", l => this.line(l, this.xScale));

        // append all paths from projected data
        this.futureLines = this.svg
            .append("g")
            .attr("fill", "none")
            .attr("stroke", "steelblue")
            .attr("stroke-width", 1.5)
            .attr("stroke-linejoin", "round")
            .attr("stroke-dasharray", "4 2")
            .selectAll("path")
            .data(this.projected)
            .join("path")
            .style("mix-blend-mode", "multiply")
            .attr("clip-path", "url(#" + this.clipId + ")")
            .attr("d", l => this.line(l, this.xScale));
    }

    _setUpZoom() {
        // set up zoom functionality
        this.zoom = d3.zoom()
            .scaleExtent([1, 32])
            .extent([[this.margin.left, 0], [this.width - this.margin.right, this.height]])
            .translateExtent([
                [this.margin.left, -Infinity], [this.width - this.margin.right, Infinity]
            ])
            .on("zoom", this._zoomed);

        // zoom out to show everything at first
        this.svg
            .call(this.zoom)
            .transition()
            .duration(750)
            .call(this.zoom.scaleTo, 0);
    }

    // event handler for zoom and drag - scale axis and apply newly scaled data to current paths
    _zoomed = () => {
        this.xZoom = d3.event.transform.rescaleX(this.xScale);
        this.pastLines.data(this.existing).call(p => p.attr("d", l => this.line(l, this.xZoom)));
        this.futureLines.data(this.projected).call(p => p.attr("d", l => this.line(l, this.xZoom)));
        this.gx.call(this.xAxis, this.xZoom);
    }

    node() {
        return this.svg.node()
    }
}
