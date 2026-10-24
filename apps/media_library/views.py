from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.core.seo import page_seo
from apps.core.views import render_page

from .models import Album, MediaKind, Video

MEDIA_CRUMB = ("Médias", "/medias/")
PER_PAGE = 12


def published(queryset):
    """Publié, et dont la date de publication (facultative) est passée."""
    return queryset.filter(is_published=True).filter(
        Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())
    )


@require_GET
def media_index(request):
    kind = request.GET.get("type")
    kinds = dict(MediaKind.choices)
    albums = (
        published(Album.objects)
        .annotate(photo_count=Count("photos"))
        .order_by("-event_date", "-pk")
    )
    videos = published(Video.objects).order_by("-published_at", "-pk")
    if kind in kinds:
        albums, videos = albums.filter(kind=kind), videos.filter(kind=kind)
    return render_page(
        request,
        "media_library/index.html",
        seo=page_seo(request, title="Médias", description="Photos et vidéos du club."),
        crumbs=[("Médias", None)],
        albums=Paginator(albums, PER_PAGE).get_page(request.GET.get("page")),
        videos=list(videos[:6]),
        kinds=MediaKind.choices,
        current_kind=kind if kind in kinds else "",
    )


@require_GET
def album_detail(request, slug):
    album = get_object_or_404(published(Album.objects), slug=slug)
    photos = list(album.photos.all())
    return render_page(
        request,
        "media_library/album_detail.html",
        seo=page_seo(
            request,
            title=album.title,
            description=f"{len(photos)} photos — {album.get_kind_display()}",
            image=album.cover or (photos[0].image if photos else None),
        ),
        crumbs=[MEDIA_CRUMB, (album.title, None)],
        album=album,
        photos=photos,
    )


@require_GET
def video_detail(request, slug):
    video = get_object_or_404(published(Video.objects), slug=slug)
    return render_page(
        request,
        "media_library/video_detail.html",
        seo=page_seo(
            request,
            title=video.title,
            description=video.description,
            image=video.thumbnail,
            type="video.other",
        ),
        crumbs=[MEDIA_CRUMB, (video.title, None)],
        video=video,
        page_jsonld={
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": video.title,
            "description": video.description or video.title,
            "embedUrl": video.embed_url,
            "uploadDate": (video.published_at or video.created_at).isoformat(),
            **(
                {"thumbnailUrl": request.build_absolute_uri(video.thumbnail.url)}
                if video.thumbnail
                else {}
            ),
        },
    )
