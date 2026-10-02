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
      color: ["#59d5bd", "#7287f9", "#d6b77b", "#557388"],
      backgroundColor: "transparent",
      textStyle: { fontFamily: "Arial", color: "#93a3b5" },
      tooltip: { trigger: scatter ? "item" : "axis" },
      legend: { bottom: 0, textStyle: { color: "#93a3b5" }, icon: "roundRect" },
      grid: { left: 52, right: 22, top: 24, bottom: 62 },
      xAxis: {
        type: scatter ? "value" : "category",
        data: labels,
        axisLine: { lineStyle: { color: "#263343" } },
        axisLabel: { color: "#7b8da2" },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#7b8da2",
          formatter: percent ? "{value}%" : undefined,
        },
        splitLine: { lineStyle: { color: "#1b2939" } },
        scale: true,
      },
      series: scatter
        ? scatter.map((s) => ({
            name: s.name,
            type: "scatter",
            symbolSize: 9,
            data: s.points,
            itemStyle: { opacity: 0.7 },
          }))
        : series?.map((s, i) => ({
            name: s.name,
            type: bar ? "bar" : "line",
            data: s.values.map((v) =>
              v === null ? null : percent ? v * 100 : v,
            ),
            smooth: false,
            symbol: "none",
            lineStyle: {
              width: i ? 1.5 : 2.5,
              type: i > 0 ? "dashed" : "solid",
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
