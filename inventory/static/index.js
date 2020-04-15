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
