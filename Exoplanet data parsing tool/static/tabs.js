//MARK: two tabs, one running app
const FinderTabThing = document.getElementById('FinderTabButton');
const ImagesTabThing = document.getElementById('ImagesTabButton');
const FinderPaneThing = document.getElementById('FinderPane');
const ImagesPaneThing = document.getElementById('ImagesPane');
let ImageImportPending = false;

function PickAppTab(Images)
{
  FinderPaneThing.hidden = Images;
  ImagesPaneThing.hidden = !Images;
  FinderTabThing.setAttribute('aria-selected', String(!Images));
  ImagesTabThing.setAttribute('aria-selected', String(Images));
  if (Images && !ImagesPaneThing.getAttribute('src'))
    ImagesPaneThing.src = '/images?embedded=1';
  if (!Images)
    DrawFlux();
}

FinderTabThing.addEventListener('click', () => PickAppTab(false));
ImagesTabThing.addEventListener('click', () => PickAppTab(true));

//MARK: bring the finished sheet back without old timing settings
async function OpenImageCurveFromImages(Url)
{
  if (BatchInProgress || RunningJobId || RequestId || JobConnectionLost)
    throw new Error('Finish or cancel the current transit batch before importing this light curve. The CSV is ready to download now.');
  const Match = String(Url).match(/^\/\?session=(images_[a-f0-9]{32})$/);
  if (!Match)
    throw new Error('Invalid image light-curve session.');
  if (ImageImportPending)
    throw new Error('A light curve is already being imported.');
  const OldSession = SessionId;
  const OldResults = FileResults;
  ImageImportPending = true;
  try
  {
    const Saved = await SaveRunNow();
    if (FileResults.some(Item => Item.result) && Saved !== true)
      throw new Error('Could not save the current results. Retry saving before importing another light curve.');
    const Reply = await fetch('/analysis-sessions/' + Match[1]);
    const Payload = await Reply.json();
    if (!Reply.ok || !Payload.state)
      throw new Error(Payload.error || 'Could not load the extracted light curve.');
    // the finder can still start work while this request is on its way.
    if (BatchInProgress || RunningJobId || RequestId || JobConnectionLost || SessionId !== OldSession || FileResults !== OldResults)
      throw new Error('The finder changed while importing. Your current results are still open; retry after the batch finishes.');
    ResultViewports.clear();
    RestoreSessionState(Payload.state);
    SessionId = Match[1];
    const NextUrl = new URL(window.location.href);
    NextUrl.searchParams.set('session', SessionId);
    window.history.replaceState(null, '', NextUrl.pathname + NextUrl.search);
    PickAppTab(false);
    SetStatus('Extracted light curve opened for inspection. Choose the source CSV again if you want to run a period search.');
    QueueSessionSave();
  }
  finally
  {
    ImageImportPending = false;
  }
}
