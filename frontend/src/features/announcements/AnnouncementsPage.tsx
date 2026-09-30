import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import ConfirmActionDialog from "@/components/ConfirmActionDialog";
import { useAppSelector } from "@/store/hooks";
import { useAnnouncements, useCreateAnnouncement, useUpdateAnnouncement, useDeleteAnnouncement } from "./useAnnouncements";
import type { Announcement } from "./announcementApi";

export default function AnnouncementsPage() {
  const role = useAppSelector((s) => s.auth.role);
  const { data: announcements, isLoading, isError } = useAnnouncements();
  const createAnnouncement = useCreateAnnouncement();
  const updateAnnouncement = useUpdateAnnouncement();
  const deleteAnnouncement = useDeleteAnnouncement();
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Announcement | null>(null);
  const [editing, setEditing] = useState<Announcement | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const { register, handleSubmit, reset } = useForm<{ title: string; body: string }>();

  const canWrite = role === "admin" || role === "hr";

  const onSubmit = async (values: { title: string; body: string }) => {
    await createAnnouncement.mutateAsync(values);
    reset();
    setOpen(false);
  };

  const openEdit = (announcement: Announcement) => {
    setEditing(announcement);
    setEditTitle(announcement.title);
    setEditBody(announcement.body);
  };

  const onSaveEdit = () => {
    if (!editing || !editTitle.trim() || !editBody.trim()) return;
    updateAnnouncement.mutate(
      { id: editing.id, data: { title: editTitle.trim(), body: editBody.trim() } },
      { onSuccess: () => setEditing(null) },
    );
  };

  return (
    <div>
      <PageHeader
        title="Announcements"
        description="Company-wide notices"
        actions={canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>New Announcement</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Announcement</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Title</Label>
                  <Input {...register("title", { required: true })} placeholder="Office closed Friday" />
                </div>
                <div className="space-y-1">
                  <Label>Body</Label>
                  <Textarea {...register("body", { required: true })} placeholder="Details..." />
                </div>
                <Button type="submit">Publish</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />

      {isLoading && <LoadingSkeleton rows={4} />}
      {isError && <p className="text-destructive">Failed to load announcements.</p>}
      {!isLoading && !isError && (
        <DataTable
          rowKey={(a: Announcement) => a.id}
          data={announcements ?? []}
          emptyTitle="No announcements yet"
          searchableText={(a) => `${a.title} ${a.body} ${a.is_active ? "active" : "hidden"}`}
          searchPlaceholder="Search announcements..."
          columns={[
            { header: "Title", render: (a) => a.title },
            { header: "Body", render: (a) => a.body },
            {
              header: "Status",
              render: (a) => (
                <Badge variant={a.is_active ? "success" : "outline"}>
                  {a.is_active ? "Active" : "Hidden"}
                </Badge>
              ),
            },
            ...(canWrite ? [{
              header: "Actions",
              render: (a: Announcement) => (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => openEdit(a)}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => updateAnnouncement.mutate({ id: a.id, data: { is_active: !a.is_active } })}
                  >
                    {a.is_active ? "Hide" : "Show"}
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => setToDelete(a)}>
                    Delete
                  </Button>
                </div>
              ),
            }] : []),
          ]}
        />
      )}
      <ConfirmActionDialog
        open={toDelete !== null}
        title="Delete announcement?"
        description={<>This will permanently delete <strong>{toDelete?.title}</strong>.</>}
        confirmLabel="Delete announcement"
        pending={deleteAnnouncement.isPending}
        error={deleteAnnouncement.isError}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !deleteAnnouncement.isPending) setToDelete(null);
        }}
        onConfirm={() => {
          if (!toDelete) return;
          deleteAnnouncement.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
        }}
      />
      <Dialog open={editing !== null} onOpenChange={(nextOpen) => !nextOpen && setEditing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Announcement</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Title</Label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Body</Label>
              <Textarea value={editBody} onChange={(e) => setEditBody(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <Button onClick={onSaveEdit} disabled={updateAnnouncement.isPending}>
                Save Changes
              </Button>
              <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
