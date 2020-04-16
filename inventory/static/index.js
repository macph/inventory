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


function calculateEnd(date, initial, average, endDate) {
    if (average) {
        const day = 1000 * 60 * 60 * 24;
        const seconds = day * initial / average;
        const newDate = date + seconds;
        if (newDate <= endDate) {
            return {date: newDate, value: 0};
        } else {
            const endValue = initial - average * (endDate - date) / day;
            return {date: endDate, value: endValue};
        }
    } else {
        return {date: endDate, value: initial};
    }
}


function collect(input) {
    const week = 1000 * 60 * 60 * 24 * 7;
    const realData = input.filter(i => i.records.length >= 2);

    const averages = realData.map(g => parseFloat(g.avg) || null);
    const dateRange = d3.extent(realData.flatMap(g => g.records.map(r => Date.parse(r.a))));
    const valueRange = [0, d3.max(realData.flatMap(g => g.records.map(r => parseFloat(r.q))))];
    const existing = realData.map(g => g.records.map(r => (
        { date: Date.parse(r.a), value: parseFloat(r.q) }
    )));

    const end = dateRange[1] + week;
    const projected = existing.map((g, i) => {
        const last = g[g.length - 1];
        const predicted = calculateEnd(last.date, last.value, averages[i], end);
        return [last, predicted];
    });

    return {
        items: realData.map(i => i.name),
        averages: averages,
        dates: dateRange,
        values: valueRange,
        existing: existing,
        projected: projected,
    };
}

function createChart(input) {
    const height = 300;
    const width = 600;
    const margin = {top: 20, right: 20, bottom: 30, left: 30};

    const data = collect(input);

    const x = d3.scaleUtc()
        .domain(data.dates)
        .range([margin.left, width - margin.right]);

    const y = d3.scaleLinear()
        .domain(data.values)
        .range([height - margin.bottom, margin.top])
        .nice();

    const xAxis = g => g
        .attr("transform", `translate(0, ${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(width / 80).tickSizeOuter(0));

    const yAxis = g => g
        .attr("transform", `translate(${margin.left}, 0)`)
        .call(d3.axisLeft(y).ticks(2))
        .call(g => g.select(".domain").remove())

    const svg = d3.create("svg")
        .attr("viewBox", [0, 0, width, height]);

    const line = d3.line()
        .defined(d => !isNaN(d.value))
        .x(d => x(d.date))
        .y(d => y(d.value));

    svg.append("g").call(xAxis);
    svg.append("g").call(yAxis);

    svg.append("g")
        .attr("fill", "none")
        .attr("stroke", "steelblue")
        .attr("stroke-width", 1.5)
        .attr("stroke-linejoin", "round")
        .selectAll("path")
        .data(data.existing)
        .join("path")
        .style("mix-blend-mode", "multiply")
        .attr("d", l => line(l));

    svg.append("g")
        .attr("fill", "none")
        .attr("stroke", "steelblue")
        .attr("stroke-width", 1.5)
        .attr("stroke-linejoin", "round")
        .attr("stroke-dasharray", "4 2")
        .selectAll("path")
        .data(data.projected)
        .join("path")
        .style("mix-blend-mode", "multiply")
        .attr("d", l => line(l));

    return svg;
}
