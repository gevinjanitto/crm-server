import React from "react";

const rings = [
  ["one", [-55, 65, 185]],
  ["two", [15, 135, 255]],
  ["three", [-25, 155]],
  ["four", [65, 245]],
];

export const OrbitBackdrop = ({ variant }) => (
  <div className={`orbit-backdrop orbit-backdrop--${variant}`} aria-hidden="true" data-testid={`orbit-backdrop-${variant}`}>
    <div className="orbit-system">
      {rings.map(([ring, angles]) => <div className={`orbit-ring orbit-ring-${ring}`} key={ring}>
        {angles.map((angle, index) => <div key={angle} className={`orbit-planet-path orbit-path-${ring}`} style={{ "--orbit-start": `${angle}deg` }}>
          <span className={`orbit-satellite ${index % 2 ? "orbit-satellite-two" : "orbit-satellite-one"}`}
            data-testid={`orbit-planet-${variant}-${ring}-${index}`} />
        </div>)}
      </div>)}
    </div>
  </div>
);