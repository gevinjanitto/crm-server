import React from "react";
import { ResponsiveContainer } from "recharts";

export const ChartFrame = ({ children, ...props }) => (
  <ResponsiveContainer
    minWidth={0}
    minHeight={0}
    initialDimension={{ width: 400, height: 190 }}
    {...props}
  >
    {children}
  </ResponsiveContainer>
);
