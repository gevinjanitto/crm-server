import React, { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, money, dateLabel } from "../lib/api";
import { Loading, ErrorState, Field, SaveButton, Badge, Empty } from "./Common";
export const ExpensesPanel = ({ p, onChange }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/expenses`),
    [types, setTypes] = useState([]),
    [form, setForm] = useState({
      cost_type_id: "",
      amount: "",
      date: new Date().toISOString().slice(0, 10),
      note: "",
    }),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState("");
  useEffect(() => {
    api
      .get("/cost-types")
      .then((r) => setTypes(r.data.filter((t) => t.active)))
      .catch(() => {});
  }, []);
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await api.post(`/projects/${p.id}/expenses`, {
        ...form,
        amount: Number(form.amount),
      });
      toast.success("Pengeluaran dicatat");
      setForm({ ...form, amount: "", note: "" });
      reload();
      onChange();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (x) => {
    if (!window.confirm("Hapus pengeluaran ini?")) return;
    try {
      await api.delete(`/projects/${p.id}/expenses/${x.id}`);
      toast.success("Pengeluaran dihapus");
      reload();
      onChange();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <div className="expenses-layout">
      <form onSubmit={save} className="panel panel-padding">
        <h2 className="detail-heading">Catat pengeluaran</h2>
        <div className="form-grid">
          <div className="form-full">
            <Field
              label="Jenis biaya"
              name="cost_type_id"
              as="select"
              options={[
                { value: "", label: "Pilih jenis biaya" },
                ...types.map((t) => ({
                  value: t.id,
                  label: `${t.name} (${t.group})`,
                })),
              ]}
              value={form.cost_type_id}
              onChange={change}
              required
            />
          </div>
          <Field
            label="Nominal (Rp)"
            name="amount"
            as="money"
            value={form.amount}
            onChange={change}
            required
          />
          <Field
            label="Tanggal"
            name="date"
            type="date"
            value={form.date}
            onChange={change}
            required
          />
          <div className="form-full">
            <Field
              label="Catatan"
              name="note"
              value={form.note}
              onChange={change}
            />
          </div>
        </div>
        {formError && (
          <p className="form-error" data-testid="expense-form-error">
            {formError}
          </p>
        )}
        <div className="form-actions">
          <SaveButton busy={busy} label="Catat pengeluaran" />
        </div>
      </form>
      <div className="panel table-wrap">
        {data.length ? (
          <table className="data-table" data-testid="expenses-table">
            <thead>
              <tr>
                <th>Tanggal</th>
                <th>Jenis biaya</th>
                <th className="hide-mobile">Catatan</th>
                <th>Nominal</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((x) => (
                <tr key={x.id} data-testid={`expense-row-${x.id}`}>
                  <td>{dateLabel(x.date)}</td>
                  <td>
                    <b>{x.cost_type_name}</b>
                    <br />
                    <Badge>{x.cost_group}</Badge>
                  </td>
                  <td className="hide-mobile">{x.note || "—"}</td>
                  <td>{money(x.amount)}</td>
                  <td>
                    <button
                      className="icon-button danger"
                      title="Hapus"
                      data-testid={`delete-expense-${x.id}`}
                      onClick={() => remove(x)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="Belum ada pengeluaran tercatat." />
        )}
      </div>
    </div>
  );
};
