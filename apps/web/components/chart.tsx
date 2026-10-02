"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { useRouter } from "next/navigation";
type Series = { name: string; values: (number | null)[] };
export function Chart({
  labels,
  series,
  scatter,
  percent = false,
  orderIds,
  title,
  bar = false,
}: {
  bar?: boolean;
  labels?: string[];
  series?: Series[];
  scatter?: { name: string; points: (number | null)[][] }[];
  percent?: boolean;
  orderIds?: string[];
  title: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption({
      color: ["#41634f", "#7a867a", "#a7a394", "#575e55"],
      backgroundColor: "transparent",
      textStyle: {
        fontFamily: "IBM Plex Sans",
        color: "#6e746b",
        fontSize: 12,
      },
      tooltip: {
        trigger: scatter ? "item" : "axis",
        backgroundColor: "#f7f6f2",
        borderColor: "#d7d8cf",
        borderWidth: 1,
        padding: [12, 16],
        textStyle: { color: "#252b27", fontSize: 12 },
        extraCssText: "border-radius:2px;box-shadow:none;",
      },
      legend: { bottom: 0, textStyle: { color: "#6e746b" }, icon: "roundRect" },
      grid: { left: 52, right: 22, top: 24, bottom: 62 },
      xAxis: {
        type: scatter ? "value" : "category",
        data: labels,
        axisLine: { lineStyle: { color: "#d7d8cf" } },
        axisLabel: { color: "#74776e" },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#74776e",
          formatter: percent ? "{value}%" : undefined,
        },
        splitLine: { lineStyle: { color: "#e6e6df" } },
        scale: !bar,
      },
      series: scatter
        ? scatter.map((s) => ({
            name: s.name,
            type: "scatter",
            symbolSize: 9,
            data: s.points,
            itemStyle: { opacity: 0.8, borderColor: "#f7f6f2", borderWidth: 1 },
          }))
        : series?.map((s, i) => ({
            name: s.name,
            type: bar ? "bar" : "line",
            data: s.values.map((v) =>
              v === null ? null : percent ? v * 100 : v,
            ),
            barMaxWidth: 36,
            itemStyle: bar ? { borderRadius: [1, 1, 0, 0] } : undefined,
            smooth: false,
            symbol: "none",
            lineStyle: {
              width: i ? 1.5 : 2.5,
              type: i === 0 ? "solid" : i === 1 ? "dashed" : "dotted",
            },
            areaStyle: i === 0 ? { opacity: 0.04 } : undefined,
          })),
    });
    chart.on("click", (event) => {
      if (orderIds?.[event.dataIndex])
        router.push(`/orders/${encodeURIComponent(orderIds[event.dataIndex])}`);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [labels, series, scatter, percent, orderIds, router, bar]);
  return <div ref={ref} className="chart" role="img" aria-label={title} />;
}
