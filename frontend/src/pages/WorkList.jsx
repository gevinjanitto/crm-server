import React, { useState } from "react";
import { useAuth } from "../App";
import { useData } from "../lib/api";
import { PageHead, AddButton, Loading, ErrorState } from "../components/Common";
import { WorkForm } from "../components/WorkComponents";
import { WorkBrowser } from "../components/WorkBrowser";
export default function WorkList({ kind }) {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData(`/work/${kind}`),
    [show, setShow] = useState(false);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const revision = kind === "revisions";
  return (
    <>
      <PageHead
        eyebrow="PROJECT CARE"
        title={revision ? "Revisi" : "Maintenance"}
        description={revision ? "Setiap masukan menjadi langkah penyempurnaan." : "Menjaga performa, merawat pengalaman digital."}
      >
        {["Admin", "Admin Project"].includes(user.role) && (
          <AddButton id="add-work" onClick={() => setShow(true)}>
            {revision ? "Revisi baru" : "Maintenance baru"}
          </AddButton>
        )}
      </PageHead>
      <WorkBrowser data={data} user={user} kind={kind} reload={reload} />
      <WorkForm open={show} onClose={() => setShow(false)} onSaved={reload} kind={kind} />
    </>
  );
}
